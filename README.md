# Website Story Scraper

A **general-purpose Python scraper** that downloads stories, blogs, and books from public websites and saves them as **PDFs** for offline reading.  
It supports **multi-page and multi-chapter scraping**, retry logic, and creates nicely formatted PDF files.

---

## Examples of supported sites
- Personal blogs (example: `https://someblog.com/posts/story-123`)
- Online book archives (example: `https://fictionexample.org/book/456`)
- Story platforms (example: `https://storiesite.net/read/789`)
- [Literotica](https://www.literotica.com) and similar story-sharing sites

*(Basically works on most text-based public sites with standard HTML `<p>` or `<div>` story content.)*

---

## Features
- Scrapes **single stories** or **entire categories/tags**
- Follows **multi-page chapters** automatically
- Auto-detects multiple HTML selectors (resilient to layout changes)
- Retries failed requests with exponential backoff
- Creates **PDFs with proper formatting**
- Skips already downloaded PDFs if re-run
- Designed for **general-purpose story scraping**, not tied to one website

---

## Requirements
- Python 3.8+ (tested on Python 3.13)
- Packages listed in `requirements.txt`

Install them:

```bash
python -m pip install -r requirements.txt
