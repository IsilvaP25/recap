import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--log-level=3")

try:
    print("Launching headless Chrome...")
    driver = webdriver.Chrome(options=chrome_options)
    
    print("Navigating to http://127.0.0.1:5000...")
    driver.get("http://127.0.0.1:5000")
    time.sleep(2)
    
    print("Clicking 'Mi Biblioteca' button...")
    # Find button by text or onclick
    buttons = driver.find_elements(By.TAG_NAME, "button")
    lib_btn = None
    for btn in buttons:
        if "Mi Biblioteca" in btn.text or "showLibrary" in btn.get_attribute("onclick"):
            lib_btn = btn
            break
            
    if lib_btn:
        lib_btn.click()
        print("Clicked 'Mi Biblioteca'. Waiting 3 seconds...")
        time.sleep(3)
        
        # Check browser console logs
        print("\n--- BROWSER CONSOLE LOGS ---")
        logs = driver.get_log("browser")
        for log in logs:
            print(log)
            
        # Inspect #libraryView element
        print("\n--- INSPECTING #libraryView ---")
        lib_view = driver.find_element(By.ID, "libraryView")
        display_style = lib_view.value_of_css_property("display")
        width = lib_view.size["width"]
        height = lib_view.size["height"]
        print(f"libraryView dimensions: {width}x{height}, display: {display_style}")
        
        # Get children
        cards = lib_view.find_elements(By.CLASS_NAME, "library-card")
        print(f"Found {len(cards)} elements with class 'library-card'")
        
        if len(cards) > 0:
            print("\nFirst card outerHTML:")
            print(cards[0].get_attribute("outerHTML")[:1000])
            print(f"First card dimensions: {cards[0].size['width']}x{cards[0].size['height']}")
            
            # Check dimensions of inner elements
            img_container = cards[0].find_element(By.CLASS_NAME, "library-card-img-container")
            content_container = cards[0].find_element(By.CLASS_NAME, "library-card-content")
            print(f"First card img_container dimensions: {img_container.size['width']}x{img_container.size['height']}")
            print(f"First card content_container dimensions: {content_container.size['width']}x{content_container.size['height']}")
    else:
        print("Could not find 'Mi Biblioteca' button!")
        
    driver.quit()
except Exception as e:
    print(f"An error occurred: {e}")
