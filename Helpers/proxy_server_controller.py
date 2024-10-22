import queue
import requests

# Initialize the queue and the list for valid proxies
q = queue.Queue()
valid_proxies = []

# Load the proxies from the file and add them to the queue
with open("requirement_descriptions_and_bug_counts/Helpers/proxy_list.txt", "r") as f:
    proxies = f.read().splitlines()  # Using splitlines() instead of split("\n") to handle newlines more reliably
    for p in proxies:
        q.put(p)

# Function to check proxies
def check_proxies():
    global q
    while not q.empty():
        proxy = q.get()
        try:
            response = requests.get(url="https://hg.mozilla.org/", proxies={"http": proxy, "https": proxy}, timeout=10)
            if response.status_code == 200:
                valid_proxies.append(proxy)
                print(f"Proxy: {proxy}. Status code: {response.status_code} (Valid)")
            else:
                print(f"Proxy: {proxy}. Status code: {response.status_code} (Invalid)")
        except requests.exceptions.ProxyError as e:
            print(f"Proxy: {proxy}. ProxyError: {e}")
        except requests.exceptions.Timeout:
            print(f"Proxy: {proxy}. Request timed out.")
        except requests.exceptions.ConnectionError:
            print(f"Proxy: {proxy}. Connection error.")
        except requests.exceptions.RequestException as e:
            print(f"Proxy: {proxy}. General error: {e}")
        finally:
            q.task_done()

if __name__ == "__main__":
    check_proxies()  # Call the proxy checker function
    print(f"Valid proxies: {valid_proxies}")
