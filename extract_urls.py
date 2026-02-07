import json

def extract_urls(json_content):
    """
    Extracts URLs from Firecrawl API map output JSON content.
    
    Args:
        json_content (dict or str): The JSON content from Firecrawl API response.
                                  Can be a dictionary or a JSON string.
    
    Returns:
        list[str]: A list of URLs found in the 'links' section of the map.
    """
    if isinstance(json_content, str):
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return []
    else:
        data = json_content
        
    urls = []
    
    # Check if 'links' key exists and is a list
    if 'links' in data and isinstance(data['links'], list):
        for item in data['links']:
            # Each item in 'links' should have a 'url' key based on API documentation/usage
            if isinstance(item, dict) and 'url' in item:
                urls.append(item['url'])
            elif isinstance(item, str):
                # Fallback in case links is just a list of strings (less common for map endpoint but possible)
                urls.append(item)
                
    return urls

if __name__ == "__main__":
    # Example usage with the file we generated earlier
    try:
        with open('firecrawl_output.json', 'r') as f:
            content = json.load(f)
            
        url_list = extract_urls(content)
        
        print(f"Found {len(url_list)} URLs.")
        print("First 5 URLs:")
        for url in url_list[:5]:
            print(url)
            
    except FileNotFoundError:
        print("firecrawl_output.json not found. Please ensure the file exists.")
