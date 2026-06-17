import json
import re
import os
import time
import requests
from decimal import Decimal
from django.db import models

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None


# --- Configuration ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"
)

OPENROUTER_FALLBACK_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-3-27b-it:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "qwen/qwen3-32b:free",
    "mistralai/mistral-7b-instruct:free",
]

HF_API_TOKEN = os.environ.get("HUGGINGFACE_API_TOKEN")
HF_MODEL = os.environ.get("HUGGINGFACE_MODEL", "meta-llama/Llama-3.2-3B-Instruct")

# Jina AI Reader - free service that converts any URL to clean text
JINA_AI_READER_URL = "https://r.jina.ai/{url}"


def get_or_create_country(country_name):
    from .models import Country

    if not country_name:
        return None
    country_name = str(country_name).strip()
    COUNTRY_ALIASES = {
        "usa": "United States",
        "united states of america": "United States",
        "us": "United States",
        "america": "United States",
        "uk": "United Kingdom",
        "britain": "United Kingdom",
        "great britain": "United Kingdom",
        "england": "United Kingdom",
        "uae": "United Arab Emirates",
        "emirates": "United Arab Emirates",
        "korea": "South Korea",
        "republic of korea": "South Korea",
        "russia": "Russia",
        "russian federation": "Russia",
        "vietnam": "Vietnam",
        "viet nam": "Vietnam",
        "iran": "Iran",
        "islamic republic of iran": "Iran",
        "syria": "Syria",
        "syrian arab republic": "Syria",
        "tanzania": "Tanzania",
        "united republic of tanzania": "Tanzania",
        "bolivia": "Bolivia",
        "plurinational state of bolivia": "Bolivia",
        "venezuela": "Venezuela",
        "bolivarian republic of venezuela": "Venezuela",
    }
    normalized = country_name.lower()
    if normalized in COUNTRY_ALIASES:
        country_name = COUNTRY_ALIASES[normalized]
    try:
        return Country.objects.get(name__iexact=country_name)
    except Country.DoesNotExist:
        pass
    try:
        return Country.objects.get(name__icontains=country_name)
    except (Country.DoesNotExist, Country.MultipleObjectsReturned):
        pass
    country, created = Country.objects.get_or_create(
        name=country_name, defaults={"code": "", "is_active": True}
    )
    return country


def resolve_countries(country_names):
    if not country_names:
        return []
    if isinstance(country_names, str):
        country_names = [
            c.strip() for c in re.split(r"[,;\n]", country_names) if c.strip()
        ]
    countries = []
    for name in country_names:
        country = get_or_create_country(name)
        if country:
            countries.append(country)
    return countries


def extract_text_from_pdf(file_path):
    text = ""
    if pdfplumber:
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception:
            pass
    if not text.strip():
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(file_path)
            for image in images:
                if pytesseract:
                    text += pytesseract.image_to_string(image) + "\n"
        except Exception:
            pass
    return text


def extract_text_from_image(file_path):
    if not pytesseract:
        raise ImportError("pytesseract not installed")
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)


def call_openrouter_llm(prompt, max_retries=3):
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY not set. Get a free key at https://openrouter.ai/keys"
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Visa Consultancy Data System",
    }

    models_to_try = [OPENROUTER_MODEL] + [
        m for m in OPENROUTER_FALLBACK_MODELS if m != OPENROUTER_MODEL
    ]

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise document data extraction assistant. Extract only the requested fields. Return valid JSON only. No markdown, no explanation.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1000,
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60,
                )

                if response.status_code == 429:
                    time.sleep(2)
                    break

                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    error_msg = result["error"].get("message", "Unknown error")
                    if (
                        "rate limit" in error_msg.lower()
                        or "quota" in error_msg.lower()
                    ):
                        break
                    raise RuntimeError(f"OpenRouter error: {error_msg}")

                return result["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                break

            except requests.exceptions.RequestException:
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                break

    raise RuntimeError(
        "All OpenRouter models failed or rate-limited. "
        "Free tier limits: ~20 req/min, ~200 req/day per model."
    )


def call_huggingface_llm(prompt, max_retries=3):
    if not HF_API_TOKEN:
        raise ValueError("HUGGINGFACE_API_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 1000,
            "temperature": 0.1,
            "return_full_text": False,
        },
    }
    fallback_models = [
        HF_MODEL,
        "microsoft/Phi-3-mini-4k-instruct",
        "HuggingFaceH4/zephyr-7b-beta",
    ]

    for model in fallback_models:
        url = f"https://api-inference.huggingface.co/models/{model}"
        for attempt in range(max_retries):
            response = None
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                if response.status_code == 503:
                    time.sleep(10 * (attempt + 1))
                    continue
                if response.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                response.raise_for_status()
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "")
                elif isinstance(result, dict):
                    return result.get("generated_text", result.get("text", ""))
                else:
                    return str(result)
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    continue
            except requests.exceptions.HTTPError:
                if (
                    response
                    and response.status_code in (503, 429)
                    and attempt < max_retries - 1
                ):
                    continue
                raise
    raise RuntimeError("All HuggingFace models failed or are loading.")


def call_llm(prompt, max_retries=3):
    errors = []

    if OPENROUTER_API_KEY:
        try:
            return call_openrouter_llm(prompt, max_retries)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    if HF_API_TOKEN:
        try:
            return call_huggingface_llm(prompt, max_retries)
        except Exception as e:
            errors.append(f"HuggingFace: {e}")

    raise RuntimeError(
        f"All LLM providers failed. Errors: {'; '.join(errors)}. "
        "Please set OPENROUTER_API_KEY or HUGGINGFACE_API_TOKEN in your .env file."
    )


def parse_document_with_llm(text, doc_type):
    prompts = {
        "passport": """Extract from this passport text. Return ONLY valid JSON:
{"full_name": "...", "nationality": "...", "date_of_birth": "YYYY-MM-DD"}""",
        "transcript": """Extract from this academic transcript. Return ONLY valid JSON:
{"institution_name": "...", "highest_qualification": "...", "graduation_year": 2023, "gpa": 8.5, "gpa_scale": 10.0}""",
        "ielts": """Extract from this IELTS scorecard. Return ONLY valid JSON:
{"ielts_overall": 7.5, "ielts_listening": 8.0, "ielts_reading": 7.5, "ielts_writing": 7.0, "ielts_speaking": 7.5, "ielts_trf_number": "...", "ielts_test_date": "YYYY-MM-DD"}""",
        "combined": """Extract all student information from these documents. Return ONLY valid JSON:
{"full_name": "...", "email": "...", "phone": "...", "nationality": "...", "highest_qualification": "...", "institution_name": "...", "graduation_year": 2023, "gpa": 8.5, "gpa_scale": 10.0, "ielts_overall": 7.5, "ielts_listening": 8.0, "ielts_reading": 7.5, "ielts_writing": 7.0, "ielts_speaking": 7.5, "ielts_trf_number": "...", "ielts_test_date": "YYYY-MM-DD", "preferred_countries": ["Country1", "Country2"]}""",
    }
    prompt_template = prompts.get(doc_type, prompts["combined"])
    full_prompt = f"""### System:
You are a precise document data extraction assistant. Extract only the requested fields. Return valid JSON only. No markdown, no explanation.

### User:
{prompt_template}

Document text:
{text[:3000]}

### Assistant:
"""
    raw_response = call_llm(full_prompt)
    content = raw_response.strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Could not parse JSON: {content[:200]}")


def validate_extracted_data(data):
    cleaned = {}
    for field in [
        "full_name",
        "email",
        "phone",
        "nationality",
        "institution_name",
        "highest_qualification",
        "ielts_trf_number",
    ]:
        if field in data and data[field]:
            cleaned[field] = str(data[field]).strip()

    # GPA fields - ensure defaults so student creation doesn't crash
    if "gpa" in data and data["gpa"]:
        try:
            cleaned["gpa"] = float(str(data["gpa"]).replace(",", "."))
        except ValueError:
            cleaned["gpa"] = 0.0
    else:
        cleaned["gpa"] = 0.0

    if "gpa_scale" in data and data["gpa_scale"]:
        try:
            cleaned["gpa_scale"] = float(str(data["gpa_scale"]).replace(",", "."))
        except ValueError:
            cleaned["gpa_scale"] = 4.0
    else:
        cleaned["gpa_scale"] = 4.0

    for field in [
        "ielts_overall",
        "ielts_listening",
        "ielts_reading",
        "ielts_writing",
        "ielts_speaking",
    ]:
        if field in data and data[field]:
            try:
                score = float(str(data[field]).replace(",", "."))
                if 0 <= score <= 9:
                    cleaned[field] = score
            except ValueError:
                pass

    if "graduation_year" in data and data["graduation_year"]:
        try:
            year = int(str(data["graduation_year"]))
            if 1950 <= year <= 2030:
                cleaned["graduation_year"] = year
        except ValueError:
            pass

    if "ielts_test_date" in data and data["ielts_test_date"]:
        date_str = str(data["ielts_test_date"])
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
            try:
                from datetime import datetime

                parsed = datetime.strptime(date_str, fmt)
                cleaned["ielts_test_date"] = parsed.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    if "preferred_countries" in data and data["preferred_countries"]:
        countries = data["preferred_countries"]
        if isinstance(countries, str):
            countries = [c.strip() for c in re.split(r"[,;\n]", countries) if c.strip()]
        cleaned["preferred_countries"] = countries

    return cleaned


def process_document_upload(upload_instance):
    try:
        upload_instance.status = "processing"
        upload_instance.save()
        file_path = upload_instance.file.path
        if file_path.lower().endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        else:
            text = extract_text_from_image(file_path)
        if not text.strip():
            raise ValueError("No text could be extracted")
        extracted = parse_document_with_llm(text, upload_instance.doc_type)
        cleaned = validate_extracted_data(extracted)
        upload_instance.extracted_data = cleaned
        upload_instance.status = "review"
        upload_instance.save()
        return cleaned
    except Exception as e:
        upload_instance.status = "failed"
        upload_instance.processing_error = str(e)
        upload_instance.save()
        raise


def create_student_from_extracted(upload_instance, confirmed_data=None):
    from .models import Student

    data = confirmed_data or upload_instance.extracted_data or {}

    # Set defaults for missing required fields
    defaults = {
        "full_name": data.get("full_name", "Unknown Student"),
        "email": data.get("email", f"unknown_{upload_instance.id}@placeholder.com"),
        "phone": data.get("phone", "0000000000"),
        "highest_qualification": data.get("highest_qualification", "Not Specified"),
        "institution_name": data.get("institution_name", "Not Specified"),
        "graduation_year": data.get("graduation_year", 2024),
        "gpa": data.get("gpa", 0.0),
        "gpa_scale": data.get("gpa_scale", 4.0),
        "preferred_intake_month": "September",
        "preferred_intake_year": 2025,
        "scholarship_priority": 3,
        "ranking_priority": 3,
        "stage": "lead",
    }

    for key, val in defaults.items():
        if key not in data or data[key] is None or data[key] == "":
            data[key] = val

    nationality_country = None
    if "nationality" in data and data["nationality"]:
        nationality_country = get_or_create_country(data["nationality"])

    preferred_countries = []
    if "preferred_countries" in data and data["preferred_countries"]:
        preferred_countries = resolve_countries(data["preferred_countries"])

    valid_fields = {
        f.name for f in Student._meta.get_fields() if isinstance(f, models.Field)
    }
    cleaned_data = {k: v for k, v in data.items() if k in valid_fields}
    cleaned_data.pop("nationality", None)
    cleaned_data.pop("preferred_countries", None)

    if nationality_country:
        cleaned_data["nationality"] = nationality_country

    student = Student.objects.create(**cleaned_data)

    if preferred_countries:
        student.preferred_countries.set(preferred_countries)

    student._preferred_countries_json = data.get("preferred_countries", [])
    student.save(update_fields=["_preferred_countries_json"])

    upload_instance.parsed_student = student
    upload_instance.status = "confirmed"
    upload_instance.save()

    return student


# --- WEBSITE SCRAPING WITH JINA AI READER ---

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


def fetch_website_text(url, max_chars=7000):
    """
    Extract clean text from any URL using Jina AI Reader (free, no API key).
    Falls back to raw requests + BeautifulSoup if Jina fails.
    """
    # Try Jina AI Reader first - it handles JS rendering, removes ads/nav
    jina_url = JINA_AI_READER_URL.format(url=url)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; VisaConsultancyBot/1.0)"}

    try:
        resp = requests.get(jina_url, headers=headers, timeout=30)
        if resp.status_code == 200:
            text = resp.text
            # Jina returns clean text - just truncate
            lines = [
                line.strip()
                for line in text.splitlines()
                if line.strip() and len(line.strip()) > 2
            ]
            return "\n".join(lines)[:max_chars]
    except Exception:
        pass  # Fallback to manual scraping

    # Fallback: raw requests + BeautifulSoup
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch website: {e}")

    if not BeautifulSoup:
        raise ImportError(
            "beautifulsoup4 not installed. Run: pip install beautifulsoup4"
        )

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(
        ["script", "style", "nav", "footer", "header", "aside", "noscript"]
    ):
        tag.decompose()

    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|main"))
    )
    if main_content:
        text = main_content.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and len(line.strip()) > 2
    ]
    return "\n".join(lines)[:max_chars]


def parse_university_website_with_llm(text):
    prompt = """Extract university program details from this website text. Return ONLY valid JSON with this exact structure:
{"program_name": "...", "degree_level": "Master", "duration_months": 24, "tuition_usd": 20000, "min_ielts": 6.5, "min_gpa_4": 3.0, "scholarship_available": true, "accepts_backlogs": true, "max_gap_years": 5, "requires_gre": false, "requires_work_exp": false, "work_exp_months": 0, "min_funds_usd": 25000, "funds_held_days_required": 28, "intake_months": ["September", "January"], "ranking_qs": 100, "accreditation": "...", "city": "...", "country": "..."}
Use null or omit fields if not found. Return JSON only, no markdown."""
    full_prompt = f"""### System:
You are a precise data extraction assistant. Extract university program details from website text.

### User:
{prompt}

Website text:
{text}

### Assistant:
"""
    raw = call_llm(full_prompt)
    content = raw.strip()
    content = re.sub(r"^```json\s*", "", content)
    content = re.sub(r"^```\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Could not parse JSON: {content[:200]}")


def validate_university_data(data):
    cleaned = {}
    for field in ["program_name", "degree_level", "accreditation", "city"]:
        if data.get(field):
            cleaned[field] = str(data[field]).strip()
    if data.get("country"):
        country = get_or_create_country(data["country"])
        if country:
            cleaned["country"] = country
    for field in [
        "scholarship_available",
        "accepts_backlogs",
        "requires_gre",
        "requires_work_exp",
    ]:
        if field in data and data[field] is not None:
            cleaned[field] = bool(data[field])
    for field in [
        "duration_months",
        "tuition_usd",
        "max_gap_years",
        "work_exp_months",
        "min_funds_usd",
        "funds_held_days_required",
        "ranking_qs",
    ]:
        if data.get(field) is not None:
            try:
                cleaned[field] = int(float(str(data[field]).replace(",", "")))
            except ValueError:
                pass
    for field in ["min_ielts", "min_gpa_4"]:
        if data.get(field) is not None:
            try:
                cleaned[field] = float(str(data[field]).replace(",", "."))
            except ValueError:
                pass
    if data.get("intake_months"):
        if isinstance(data["intake_months"], list):
            cleaned["intake_months"] = [
                m for m in data["intake_months"] if isinstance(m, str)
            ]
        elif isinstance(data["intake_months"], str):
            cleaned["intake_months"] = [
                m.strip() for m in data["intake_months"].split(",") if m.strip()
            ]
    return cleaned


def scrape_university_website(university):
    from django.utils import timezone
    from .models import University

    if not university.website:
        raise ValueError("University has no website URL")

    text = fetch_website_text(university.website)
    extracted = parse_university_website_with_llm(text)
    cleaned = validate_university_data(extracted)

    valid_fields = {f.name for f in University._meta.get_fields()}
    updated = []
    for field, value in cleaned.items():
        if field in valid_fields and value is not None:
            setattr(university, field, value)
            updated.append(field)

    university.data_source = "ai_scraped"
    university.last_verified_date = timezone.now().date()
    university.save()

    return updated
