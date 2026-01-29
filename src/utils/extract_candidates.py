import os, re, csv, uuid, json, argparse
from typing import Dict, Any, List
from pdfminer.high_level import extract_text as pdf_extract_text
from docx import Document as DocxDocument
from rapidfuzz import process, fuzz
import boto3

# --------- config ---------
TARGET_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
# MODEL_ID = os.getenv("MODEL_ID", "us.anthropic.claude-3-7-sonnet-20250219-v1:0")
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

OUT_COLUMNS = [
    "candidate_id","name","location","availability","years_total","skills_text","summary_text"
]

ONTOLOGY_PATH = os.getenv("ONTOLOGY_PATH", "skills_ontology.json")

def load_ontology():
    with open(ONTOLOGY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    aliases = {k.lower(): v.lower() for k, v in data.get("aliases", {}).items()}
    canonical = set()
    for k, arr in data.items():
        if k == "aliases": continue
        for s in arr:
            canonical.add(s.lower())
    return aliases, canonical

ALIASES, CANONICAL = load_ontology()

# --------------------------------

def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def read_docx(path: str) -> str:
    doc = DocxDocument(path)
    return "\n".join(p.text for p in doc.paragraphs)

def read_pdf(path: str) -> str:
    return pdf_extract_text(path)

def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_txt(path)
    if ext == ".docx":
        return read_docx(path)
    if ext == ".pdf":
        return read_pdf(path)
    raise ValueError(f"Unsupported file type: {ext}")

# Lightweight, best-effort regex helpers (used as hints/fallbacks)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}")
LOCATION_WORDS = {"india","usa","united states","canada","europe","remote","hybrid","bangalore","bengaluru",
                  "mumbai","pune","delhi","hyderabad","chennai","gurgaon","noida"}

def fuzzy_normalize_skills(raw: str) -> List[str]:
    # Split on common separators
    tokens = [t.strip().lower() for t in re.split(r"[,\n;|/]", raw) if t.strip()]
    out = set()
    for t in tokens:
        # 1) alias map
        if t in ALIASES:
            t = ALIASES[t]
        # 2) direct canonical
        if t in CANONICAL:
            out.add(t)
            continue
        # 3) fuzzy to nearest canonical (optional)
        match, score, _ = process.extractOne(t, list(CANONICAL), scorer=fuzz.token_sort_ratio)
        if score >= 86:
            out.add(match)
        else:
            # keep unknown techish tokens (shortlist)
            if re.search(r"[a-z][a-z0-9\.\+#\-]{1,}", t) and len(t) <= 30:
                out.add(t)
    return sorted(out)


def bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name="us-east-1"
    )


def call_bedrock_claude(text: str) -> Dict[str, Any]:
    """
    Ask the model to emit STRICT JSON with our fields.
    """
    system = (
        "You are an expert resume parser and summarizer. "
        "Extract factual data from the provided resume text. "
        "Return STRICT JSON with keys: name, location, availability, years_total, skills_text, summary_text. "
        "years_total must be a number (float). skills_text must be a short comma-separated list of skills. "
        "If a field is missing, infer a concise and realistic value from the resume. "
        "summary_text must be a brief professional summary (1–2 sentences), derived strictly from the resume content."
    )

    user = (
        "Resume text:\n```\n" + text[:100000] + "\n```\n"
        "Emit JSON ONLY. Example:\n"
        "{\n"
        '  "name": "Jane Doe",\n'
        '  "location": "Bengaluru, India",\n'
        '  "availability": "Immediate",\n'
        '  "years_total": 6.5,\n'
        '  "skills_text": "python, fastapi, aws, docker",\n'
        '  "summary_text": "Senior Python engineer with 6+ years. Built FastAPI services on AWS (Lambda, API GW)."\n'
        "}"
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0,
        "system": system,
        "messages": [{"role":"user","content":[{"type":"text","text":user}]}]
    })

    client = bedrock_client()
    resp = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    payload = json.loads(resp["body"].read())
    # Claude returns content array with text in the first item
    content = payload.get("content", [])
    text_out = ""
    if content and isinstance(content, list) and "text" in content[0]:
        text_out = content[0]["text"]
    # Trim any code fences or stray text
    json_str = text_out.strip().strip("`").strip()
    # Try to find the first {...} block if the model added notes
    m = re.search(r"\{.*\}", json_str, flags=re.DOTALL)
    if m:
        json_str = m.group(0)
    try:
        return json.loads(json_str)
    except Exception:
        # Fallback: very basic heuristic extraction
        name = ""
        email = EMAIL_RE.search(text)
        phone = PHONE_RE.search(text)
        # naive name guess (first non-empty line with spaces, not an email/phone)
        for line in text.splitlines():
            l = line.strip()
            if len(l.split()) >= 2 and not EMAIL_RE.search(l) and not PHONE_RE.search(l):
                name = l
                break
        return {
            "name": name[:120],
            "location": "",
            "availability": "",
            "years_total": "",
            "skills_text": "",
            "summary_text": ""
        }

def normalize_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Coerce fields + normalize skills
    name = (raw.get("name") or "").strip()
    location = (raw.get("location") or "").strip()
    availability = (raw.get("availability") or "").strip()
    years_raw = raw.get("years_total")
    try:
        years_total = float(years_raw) if years_raw is not None else 0.0
    except Exception:
        # Try to pull a number from text, e.g., "6+ years"
        yrs = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*years", json.dumps(raw), re.I)
        years_total = float(yrs.group(1)) if yrs else ""
    skills_text_raw = (raw.get("skills_text") or "")
    skills_norm = ", ".join(fuzzy_normalize_skills(skills_text_raw))
    summary_text = (raw.get("summary_text") or "").strip()
    return {
        "name": name[:120],
        "location": location[:120],
        "availability": availability[:120],
        "years_total": years_total,
        "skills_text": skills_norm[:500],
        "summary_text": summary_text[:1500]
    }

def process_resume(path: str) -> Dict[str, Any]:
    txt = extract_text(path)
    parsed = call_bedrock_claude(txt)
    norm = normalize_record(parsed)
    row = {
        "candidate_id": str(uuid.uuid4()),
        **norm
    }
    return row


# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument(
#         "--input_dir",
#         default=None,
#         help="Folder with resumes (.pdf/.docx/.txt)"
#     )
#     ap.add_argument(
#         "--text_file",
#         default=None,
#         help="A text file containing raw resume text"
#     )
#     ap.add_argument(
#         "--text",
#         default=None,
#         help="Raw resume text passed as a string"
#     )
#     ap.add_argument(
#         "--out_csv",
#         default="candidates.csv"
#     )
#     args = ap.parse_args()

#     rows = []

#     # ------------------------------------
#     # OPTION 1: Raw text passed directly
#     # ------------------------------------
#     if args.text:
#         record = normalize_record(call_bedrock_claude(args.text))
#         rows.append({"candidate_id": str(uuid.uuid4()), **record})
#         print("✓ Parsed text input →", record["name"])
    
#     # ------------------------------------
#     # OPTION 2: Process a text file
#     # ------------------------------------
#     elif args.text_file:
#         txt = read_txt(args.text_file)
#         record = normalize_record(call_bedrock_claude(txt))
#         rows.append({"candidate_id": str(uuid.uuid4()), **record})
#         print(f"✓ Parsed text file {args.text_file} → {record['name']}")

#     # ------------------------------------
#     # OPTION 3: Process resume files from a directory
#     # ------------------------------------
#     elif args.input_dir:
#         for fname in os.listdir(args.input_dir):
#             if not fname.lower().endswith((".pdf", ".docx", ".txt")):
#                 continue
#             path = os.path.join(args.input_dir, fname)
#             try:
#                 record = process_resume(path)
#                 rows.append(record)
#                 print(f"✓ Parsed {fname} → {record['name']} ({record['years_total']})")
#             except Exception as e:
#                 print(f"✗ Failed {fname}: {e}")
#     else:
#         print("Error: You must provide --text, --text_file, or --input_dir")
#         return

#     # ------------------------------------
#     # Write output CSV
#     # ------------------------------------
#     if not rows:
#         print("No rows parsed.")
#         return

#     with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
#         w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
#         w.writeheader()
#         for r in rows:
#             w.writerow({k: r.get(k, "") for k in OUT_COLUMNS})

#     print(f"Done. Wrote {len(rows)} rows to {args.out_csv}")

# if __name__ == "__main__":
#     main()
