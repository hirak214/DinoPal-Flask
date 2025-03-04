links = ['https://www.searchmetrics.com › Glossary Item', '', '', '', '', '', '', '', '', '', 'https://www.reliablesoft.net › what-are-search-terms', '', 'https://www.wordstream.com › Learn', '', 'https://www.semrush.com › blog › search-terms', '', 'https://yoast.com › SEO blog › SEO basics', '', 'https://www.opentracker.net › choosing-search-terms', '', 'https://support.google.com › google-ads › answer', '', 'https://blog.hubspot.com › marketing › how-to-do-key...', '', 'https://www.dopinger.com › blog › what-is-a-search-term', '']




def get_urls(num_of_links, links):
    links = [link for link in links if link]

    extracted_links = []
    for link in links:
        url = link.split(" ")[0]
        extracted_links.append(url)

    # step 3: make a new list for the urls
    urls = extracted_links
    return urls[:num_of_links]