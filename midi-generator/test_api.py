import requests
import sys
import os

def test_api(url, file_path):
    print(f"Testing API at {url} with file {file_path}")
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{url}/process", files=files)
        
        if response.status_code == 200:
            print("Success! Received MIDI file.")
            with open("output_test.mid", "wb") as f:
                f.write(response.content)
            print("Saved to output_test.mid")
        else:
            print(f"Failed with status code {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_api.py <api_url> <mp3_file_path>")
        print("Example: python test_api.py http://localhost:8000 test.mp3")
        sys.exit(1)
        
    url = sys.argv[1]
    file_path = sys.argv[2]
    test_api(url, file_path)
