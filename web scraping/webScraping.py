import os
import re
from bs4 import BeautifulSoup
import pandas as pd
from playwright.sync_api import sync_playwright

# Configuration
base_url = 'https://journals.sagepub.com'  # Base URL for the site
html_directory = '.'  # Directory where the HTML files will be saved

def extract_links(page):
    """
    Extract all article links from the main table of contents page.
    The links start with '/doi/abs/' and are specific to each article.
    
    Args:
        page: The page object from Playwright representing the TOC page.

    Returns:
        List of hrefs (URLs) extracted from the page.
    """
    links = page.query_selector_all('a[href^="/doi/abs/"]')  
    hrefs = [link.get_attribute('href') for link in links]  # Extract href attributes
    return hrefs

def process_page(url, browser):
    """
    Visit the article page and retrieve its HTML content.
    
    Args:
        url: The full URL of the article page.
        browser: The Playwright browser object.

    Returns:
        HTML content of the page as a string.
    """
    page = browser.new_page()  # Create a new page in the browser
    page.goto(url)  # Navigate to the article URL
    page.wait_for_load_state('networkidle')  # Wait for the page to fully load (no network requests)
    html_content = page.content()  # Get the HTML content of the page
    page.close()  # Close the page
    return html_content

def extract_title_from_html(file_path):
    """
    Extract the title of the article from the HTML file.
    
    Args:
        file_path: Path to the saved HTML file.

    Returns:
        Title of the article or None if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')  # Parse HTML content
        meta_tag = soup.find('meta', attrs={'name': 'dc.Title'})  # Find the meta tag with the title
        if meta_tag and 'content' in meta_tag.attrs:
            return meta_tag['content']  # Return title if found
        return None

def extract_authors_from_html(file_path):
    """
    Extract the author names and their affiliations from the HTML file, replacing email addresses and parentheses with periods.
    
    Args:
        file_path: Path to the saved HTML file.

    Returns:
        String of concatenated authors and affiliations with email addresses and parentheses replaced by periods, or None if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')  # Parse HTML content
        author_divs = soup.find_all('div', id=lambda x: x and x.startswith('corresp1-'))  # Find author divs
        authors = [div.get_text(strip=True) for div in author_divs]  # Extract text for each author
        
        # Replace email addresses and parentheses with periods
        authors_cleaned = [re.sub(r'\s*email:[^\s]+', '.', author) for author in authors]
        authors_cleaned = [re.sub(r'\s*\(', '.', author) for author in authors_cleaned]  # Replace opening parentheses with period
        authors_cleaned = [re.sub(r'\)\s*', '.', author) for author in authors_cleaned]  # Replace closing parentheses with period
        
        return ' '.join(authors_cleaned) if authors_cleaned else None  # Concatenate authors if found



def extract_publication_date_from_html(file_path):
    """
    Extract the article's publication date from the HTML file.
    
    Args:
        file_path: Path to the saved HTML file.

    Returns:
        Publication date or None if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')  # Parse HTML content
        core_history_div = soup.find('div', class_='core-history')  # Find the history section
        if core_history_div:
            for div in core_history_div.find_all('div'):
                label = div.find('b', class_='core-label')  # Look for the label indicating the date
                if label and 'Article first published online' in label.get_text():
                    return div.get_text(strip=True).split(':', 1)[1].strip()  # Extract and clean the date
        return None

def extract_doi_from_html(file_path):
    """
    Extract the article's DOI from the JavaScript embedded in the HTML file.
    
    Args:
        file_path: Path to the saved HTML file.

    Returns:
        DOI or None if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')  # Parse HTML content
        script_tags = soup.find_all('script')  # Find all script tags
        for script in script_tags:
            if script.string and 'var journalAdParams =' in script.string:
                # Use regular expression to search for the DOI within the script
                doi_match = re.search(r"doi\s*:\s*'([^']+)'", script.string)
                if doi_match:
                    return doi_match.group(1)  # Return DOI if found
        return None

def extract_abstract_from_html(file_path):
    """
    Extract the article's abstract from the HTML file.
    
    Args:
        file_path: Path to the saved HTML file.

    Returns:
        Abstract text or None if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')  # Parse HTML content
        abstract_section = soup.find('section', id='abstract')  # Find the abstract section
        if abstract_section:
            abstract_div = abstract_section.find('div', role='paragraph')  # Find the abstract paragraph
            if abstract_div:
                return abstract_div.get_text(strip=True)  # Extract the abstract text
        return None

def main():
    """
    Main function to extract article data and save it to a CSV file.
    It uses Playwright to navigate the website, extract data, and save it.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Launch the browser in non-headless mode
        main_page = browser.new_page()  # Create a new page

        # Go to the main page containing the table of contents (TOC)
        main_page.goto('https://journals.sagepub.com/toc/JMX/current')
        main_page.wait_for_load_state('networkidle')  # Wait until the page fully loads

        # Extract all article links from the TOC page
        hrefs = extract_links(main_page)

        # Process each article link and save HTML content
        for i, href in enumerate(hrefs, start=1):
            full_url = base_url + href  # Construct the full URL for the article
            html_content = process_page(full_url, browser)  # Get HTML content of the article
            
            # Save the HTML content to a file
            filename = f'page_{i}.html'
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(html_content)

        browser.close()  # Close the browser

    # Extract data from saved HTML files and save it to a CSV
    data = []
    
    for filename in os.listdir(html_directory):
        if filename.endswith('.html'):
            file_path = os.path.join(html_directory, filename)  # Construct file path
            title = extract_title_from_html(file_path)  # Extract title
            authors = extract_authors_from_html(file_path)  # Extract authors
            publication_date = extract_publication_date_from_html(file_path)  # Extract publication date
            doi = extract_doi_from_html(file_path)  # Extract DOI
            abstract = extract_abstract_from_html(file_path)  # Extract abstract
            if title:
                data.append({
                    'Title': title, 
                    'Authors With Their Affliations': authors, 
                    'Publication_date': publication_date, 
                    'DOI': doi, 
                    'Abstract': abstract
                })
            # Delete the HTML file after processing
            os.remove(file_path)  # Remove the HTML file after extracting data
    
    # Create a DataFrame and save the extracted data to a CSV file
    df = pd.DataFrame(data)
    df.to_csv('scraped_data.csv', index=False)  # Save data to CSV
    print("Titles, authors, publication dates, DOIs, and abstracts saved to Scraped_data.csv")

if __name__ == "__main__":
    main()  # Run the main function
