import os
import re
import time  
from bs4 import BeautifulSoup
import pandas as pd
from playwright.sync_api import sync_playwright

# Configuration
base_url = 'https://journals.sagepub.com'  # Base URL for the site
html_directory = '.'  # Directory where the HTML files will be saved

def extract_links(page):
    links = page.query_selector_all('a[href^="/doi/abs/"]')  
    hrefs = [link.get_attribute('href') for link in links]
    return hrefs

def process_page(url, browser):
    page = browser.new_page()
    page.goto(url)
    page.wait_for_load_state('networkidle')
    html_content = page.content()
    page.close()
    return html_content

def extract_title_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        meta_tag = soup.find('meta', attrs={'name': 'dc.Title'})
        if meta_tag and 'content' in meta_tag.attrs:
            return meta_tag['content']
        return None

def extract_authors_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        author_divs = soup.find_all('div', id=lambda x: x and x.startswith('corresp1-'))
        authors = [div.get_text(strip=True) for div in author_divs]
        authors_cleaned = [re.sub(r'\s*email:[^\s]+', '.', author) for author in authors]
        authors_cleaned = [re.sub(r'\s*\(', '.', author) for author in authors_cleaned]
        authors_cleaned = [re.sub(r'\)\s*', '.', author) for author in authors_cleaned]
        return ' '.join(authors_cleaned) if authors_cleaned else None

def extract_publication_date_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        core_history_div = soup.find('div', class_='core-history')
        if core_history_div:
            for div in core_history_div.find_all('div'):
                label = div.find('b', class_='core-label')
                if label and 'Article first published online' in label.get_text():
                    return div.get_text(strip=True).split(':', 1)[1].strip()
        return None

def extract_doi_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and 'var journalAdParams =' in script.string:
                doi_match = re.search(r"doi\s*:\s*'([^']+)'", script.string)
                if doi_match:
                    return doi_match.group(1)
        return None

def extract_abstract_from_html(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')
        abstract_section = soup.find('section', id='abstract')
        if abstract_section:
            abstract_div = abstract_section.find('div', role='paragraph')
            if abstract_div:
                return abstract_div.get_text(strip=True)
        return None

def main():
    start_time = time.time()  # Start the timer
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        main_page = browser.new_page()

        # Go to the main page containing the table of contents (TOC)
        main_page.goto('https://journals.sagepub.com/toc/JMX/current')
        main_page.wait_for_load_state('networkidle')

        # Extract all article links from the TOC page
        hrefs = extract_links(main_page)

        # Process each article link and save HTML content
        for i, href in enumerate(hrefs, start=1):
            full_url = base_url + href
            html_content = process_page(full_url, browser)
            
            # Save the HTML content to a file
            filename = f'page_{i}.html'
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(html_content)

        browser.close()

    # Extract data from saved HTML files and save it to a CSV
    data = []
    
    for filename in os.listdir(html_directory):
        if filename.endswith('.html'):
            file_path = os.path.join(html_directory, filename)
            title = extract_title_from_html(file_path)
            authors = extract_authors_from_html(file_path)
            publication_date = extract_publication_date_from_html(file_path)
            doi = extract_doi_from_html(file_path)
            abstract = extract_abstract_from_html(file_path)
            if title:
                data.append({
                    'Title': title, 
                    'Authors With Their Affliations': authors, 
                    'Publication_date': publication_date, 
                    'DOI': doi, 
                    'Abstract': abstract
                })
            # Delete the HTML file after processing
            os.remove(file_path)
    
    # Create a DataFrame and save the extracted data to a CSV file
    df = pd.DataFrame(data)
    df.to_csv('scraped_data.csv', index=False)

    end_time = time.time()  # Stop the timer
    total_time = end_time - start_time
    print(f"Data extraction and saving completed in {total_time:.2f} seconds.")

if __name__ == "__main__":
    main()
