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
    
    # Check parent elements
    elements = {
        "body": driver.find_element(By.TAG_NAME, "body"),
        ".layout": driver.find_element(By.CLASS_NAME, "layout"),
        "main.gallery-container": driver.find_element(By.CLASS_NAME, "gallery-container"),
        ".gallery-body": driver.find_element(By.CLASS_NAME, "gallery-body"),
        "#libraryView": driver.find_element(By.ID, "libraryView")
    }
    
    print("--- Dimensions and Display ---")
    for name, el in elements.items():
        w = el.size["width"]
        h = el.size["height"]
        disp = el.value_of_css_property("display")
        flex = el.value_of_css_property("flex")
        overflow = el.value_of_css_property("overflow")
        print(f"{name}: {w}x{h}, display: {disp}, flex: {flex}, overflow: {overflow}")
        
    driver.quit()
except Exception as e:
    print(f"Error: {e}")
