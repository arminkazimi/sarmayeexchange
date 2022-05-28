import requests
base = 'http://127.0.0.1:5000/'
body = ''
headers = {"Content-Type":"application/json","method":"z_process"}

response = requests.post(base, body,headers=headers)
print(response.json())