# ContentRepurposer

Here’s a concise summary you can use for your repo README or project description:

---

## Project Summary

This project demonstrates a workflow for scraping web content, summarizing it, and generating multi-platform social media and marketing content using the **OpenRouter GPT OSS 120B** model. The notebook includes:

1. **Environment Setup**

   * Loads API keys and base URLs from `.env` using `dotenv`.
   * Validates OpenRouter API key and base URL.

2. **Model Configuration**

   * Defines models for text generation:

     * `gpt-oss-120b` (primary content generation)
     * `meta-llama/llama-3.2-3b-instruct` (optional alternative)

3. **Content Scraping**

   * Uses a `scrape_site` module to extract text content from a list of URLs.


4. **Content Generation**

   * Sends scraped content to GPT OSS 120B.
   * Automatically converts long-form articles into:

     * Bite-sized LinkedIn posts
     * Twitter threads
     * Facebook posts
     * Instagram captions
     * Persuasive video ad captions
     * Informative email newsletters
   * Supports casual, engaging tones for social media and educational/ persuasive tones for ads and newsletters.

5. **Interactive Output**

   * Displays generated content in real-time using Jupyter/IPython display features.
   * Ready-to-use for copy-paste across multiple marketing channels.

---

### Key Tech Stack

* Python 3.12
* OpenRouter API + GPT OSS 120B
* `dotenv` for environment management
* IPython display tools for live streaming outputs

---

If you want, I can also draft a **short, one-paragraph version** perfect for the top of a GitHub repo so it’s immediately readable for visitors. Do you want me to do that?
