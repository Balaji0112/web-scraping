import os
import re
import time  # Import the time module to track execution time
from bs4 import BeautifulSoup
import pandas as pd
from playwright.sync_api import sync_playwright

# Configuration
base_url = 'https://journals.sagepub.com'

def extract_links(page):
    links = page.query_selector_all('a[href^="/doi/abs/"]')
    hrefs = [link.get_attribute('href') for link in links]
    return hrefs

def extract_data_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract Title
    title = None
    meta_tag = soup.find('meta', attrs={'name': 'dc.Title'})
    if meta_tag and 'content' in meta_tag.attrs:
        title = meta_tag['content']

    # Extract Authors and Affiliations
    authors = None
    author_divs = soup.find_all('div', id=lambda x: x and x.startswith('corresp1-'))
    if author_divs:
        authors = ' '.join([div.get_text(strip=True) for div in author_divs])
        authors = re.sub(r'\s*email:[^\s]+', '.', authors)
        authors = re.sub(r'\s*\(', '.', authors)
        authors = re.sub(r'\)\s*', '.', authors)

    # Extract Publication Date
    publication_date = None
    core_history_div = soup.find('div', class_='core-history')
    if core_history_div:
        for div in core_history_div.find_all('div'):
            label = div.find('b', class_='core-label')
            if label and 'Article first published online' in label.get_text():
                publication_date = div.get_text(strip=True).split(':', 1)[1].strip()

    # Extract DOI
    doi = None
    script_tags = soup.find_all('script')
    for script in script_tags:
        if script.string and 'var journalAdParams =' in script.string:
            doi_match = re.search(r"doi\s*:\s*'([^']+)'", script.string)
            if doi_match:
                doi = doi_match.group(1)

    # Extract Abstract
    abstract = None
    abstract_section = soup.find('section', id='abstract')
    if abstract_section:
        abstract_div = abstract_section.find('div', role='paragraph')
        if abstract_div:
            abstract = abstract_div.get_text(strip=True)

    return {
        'Title': title,
        'Authors With Their Affliations': authors,
        'Publication_date': publication_date,
        'DOI': doi,
        'Abstract': abstract
    }

def main():
    start_time = time.time()  # Start the timer
    
    data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        main_page = browser.new_page()
        
        # Go to the main page containing the table of contents (TOC)
        main_page.goto('https://journals.sagepub.com/toc/JMX/current')
        main_page.wait_for_load_state('networkidle')

        # Extract all article links from the TOC page
        hrefs = extract_links(main_page)

        # Process each article link
        for i, href in enumerate(hrefs, start=1):
            full_url = base_url + href
            page = browser.new_page()
            page.goto(full_url)
            page.wait_for_load_state('networkidle')
            html_content = page.content()
            page.close()

            # Extract data from the HTML content
            article_data = extract_data_from_html(html_content)
            if article_data['Title']:
                data.append(article_data)
        
        browser.close()
    
    # Create a DataFrame and save the extracted data to a CSV file
    df = pd.DataFrame(data)
    df.to_csv('scraped_data.csv', index=False)

    end_time = time.time()  # Stop the timer
    total_time = end_time - start_time
    print(f"Data extraction completed in {total_time:.2f} seconds.")

if __name__ == "__main__":
    main()
