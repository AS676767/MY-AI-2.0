
import trafilatura
import requests
from urllib.parse import urlparse
from approved_sources import APPROVED_SOURCES

HEADERS = {
    "User-Agent": "EducationalResearchAssistant/1.0"
}

def is_approved_url(url):
    """Allow URLs only from the approved website list."""
    try:
        domain = urlparse(url).hostname
        if not domain:
            return False

        for approved_url in APPROVED_SOURCES:
            approved_domain = urlparse(approved_url).hostname

            if domain == approved_domain or domain.endswith("." + approved_domain):
                return True

        return False
    except Exception:
        return False


def fetch_website_text(url):
    """Download and extract readable text from an approved webpage."""
    if not is_approved_url(url):
        return None

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type.lower():
            return None

        text = trafilatura.extract(response.text)

        if not text or len(text) < 200:
            return None

        return text

    except requests.RequestException:
        return None
    except Exception:
        return None


def search_approved_websites(urls):
    """Collect text only from URLs supplied from approved websites."""
    results = []

    for url in urls:
        if not is_approved_url(url):
            continue

        text = fetch_website_text(url)

        if text:
            results.append({
                "url": url,
                "content": text
            })

    return results

import hashlib
import chromadb
from sentence_transformers import SentenceTransformer

# Local database for collected website information
db = chromadb.PersistentClient(path="./rag_database")

collection = db.get_or_create_collection(
    name="educational_sources"
)

# Model that converts text into searchable numerical representations
embedding_model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)


def split_into_chunks(text, chunk_size=800):
    """Split webpage text into smaller sections."""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 100:
            chunks.append(chunk)

    return chunks


def add_website_to_database(url):
    """Extract an approved webpage and save its sections."""
    website_results = search_approved_websites([url])

    if not website_results:
        return "No readable content found. Check the URL and access permissions."

    website_text = website_results[0]["content"]
    chunks = split_into_chunks(website_text)

    if not chunks:
        return "No suitable text was found on this page."

    ids = []
    for index, chunk in enumerate(chunks):
        unique_id = hashlib.sha256(
            f"{url}-{index}".encode()
        ).hexdigest()
        ids.append(unique_id)

    embeddings = embedding_model.encode(chunks).tolist()

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"url": url} for _ in chunks]
    )

    return f"Saved {len(chunks)} sections from {url}"


def search_knowledge(question, number_of_results=4):
    """Find relevant saved sections for a question."""
    if collection.count() == 0:
        return []

    question_embedding = embedding_model.encode(
        [question]
    ).tolist()

    results = collection.query(
        query_embeddings=question_embedding,
        n_results=min(number_of_results, collection.count())
    )

    matches = []

    for document, metadata in zip(
        results["documents"][0],
        results["metadatas"][0]
    ):
        matches.append({
            "content": document,
            "url": metadata["url"]
        })

    return matches

import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser


def get_allowed_pages(base_url, max_pages=3):
    """Find a small number of publicly accessible pages through sitemaps."""
    parsed = urlparse(base_url)
    root_url = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(root_url, "/robots.txt")

    try:
        response = requests.get(
            robots_url, headers=HEADERS, timeout=15
        )

        if response.status_code >= 500:
            return []

        robot = RobotFileParser()
        robot.set_url(robots_url)
        robot.parse(response.text.splitlines())

        sitemap_urls = [
            line.split(":", 1)[1].strip()
            for line in response.text.splitlines()
            if line.lower().startswith("sitemap:")
        ]

        if not sitemap_urls:
            sitemap_urls = [urljoin(root_url, "/sitemap.xml")]

        pages = []

        for sitemap_url in sitemap_urls[:2]:
            if not is_approved_url(sitemap_url):
                continue

            sitemap_response = requests.get(
                sitemap_url, headers=HEADERS, timeout=15
            )
            sitemap_response.raise_for_status()

            xml_root = ET.fromstring(sitemap_response.content)

            for element in xml_root.iter():
                if element.tag.endswith("loc") and element.text:
                    page_url = element.text.strip()

                    if (
                        is_approved_url(page_url)
                        and robot.can_fetch(
                            HEADERS["User-Agent"], page_url
                        )
                        and page_url not in pages
                    ):
                        pages.append(page_url)

                    if len(pages) >= max_pages:
                        return pages

        return pages

    except Exception:
        return []


def bulk_import_approved_sources(max_pages_per_site=3):
    """Import a limited number of permitted pages from each approved site."""
    imported = 0
    skipped = 0
    details = []

    for website in APPROVED_SOURCES:
        pages = get_allowed_pages(
            website, max_pages=max_pages_per_site
        )

        if not pages:
            skipped += 1
            continue

        for page_url in pages:
            result = add_website_to_database(page_url)

            if result.startswith("Saved"):
                imported += 1
                details.append(result)

    return {
        "imported": imported,
        "skipped": skipped,
        "details": details
    }

