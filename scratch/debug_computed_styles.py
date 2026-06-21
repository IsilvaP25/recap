import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--log-level=3")

try:
    driver = webdriver.Chrome(options=chrome_options)
    driver.get("http://127.0.0.1:5000")
    time.sleep(2)
    
    # Click 'Mi Biblioteca'
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        if "Mi Biblioteca" in btn.text or "showLibrary" in btn.get_attribute("onclick"):
            btn.click()
            break
            
    time.sleep(3)
    
    # Get first library card
    card = driver.find_element(By.CLASS_NAME, "library-card")
    print(f"Card dimensions: {card.size['width']}x{card.size['height']}")
    
    # Get computed styles
    properties = ["display", "height", "min-height", "max-height", "position", "overflow", "flex-direction", "box-sizing"]
    print("\n--- Card Computed Styles ---")
    for prop in properties:
        val = card.value_of_css_property(prop)
        print(f"{prop}: {val}")
        
    print("\n--- Img Container Computed Styles ---")
    img_container = card.find_element(By.CLASS_NAME, "library-card-img-container")
    print(f"Img Container dimensions: {img_container.size['width']}x{img_container.size['height']}")
    for prop in ["display", "height", "min-height", "max-height", "position", "overflow", "padding-top", "aspect-ratio"]:
        val = img_container.value_of_css_property(prop)
        print(f"{prop}: {val}")
        
    driver.quit()
except Exception as e:
    print(f"Error: {e}")
