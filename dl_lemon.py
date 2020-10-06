import requests, os

# Just downright download lemon.py from my github repository whenever this is imported
if not os.path.exists('./lemon.py'):
    with open('./lemon.py', 'w') as file:
        print('Downloading ./lemon.py...')
        file.write(requests.get('https://raw.githubusercontent.com/Pop101/Lemon/master/lemon.py').text)