import json
import subprocess
import os
from urllib.parse import urlparse
import re


JSON_FILE = "bitwarden_export.json"


def get_valid_directory_name(input_string):
    invalid_chars = r'[\/:*?"<>|\\]'
    match = re.search(invalid_chars, input_string)

    if match:
        return input_string[:match.start()]
    else:
        return input_string


def main():
    with open(JSON_FILE, "r", encoding="utf-8") as jsonfile:
        data = json.load(jsonfile)
        items = data.get("items", [])

        name_to_items = {}
        id = 1
        
        for item in items:
            if "login" in item and "password" in item.get("login", {}):

                login = item.get("login", {})
                name = item.get("name", "")
                if not login or not isinstance(login, dict):
                    continue

                uris = login.get("uris", [])
                login_uri = ""
                if uris:
                    login_uri = (uris[0].get("uri") or "").strip()
                username = (login.get("username") or "").strip()
                password = (login.get("password") or "").strip()

                if not password:
                    continue

                if not name and login_uri:
                    name = urlparse(login_uri).netloc

                if not name and not login_uri:
                    name = '«unknown»'

                name = get_valid_directory_name(name)

                content = f"{password}\n".rstrip()
                if username: 
                    content += f"\nusername:{username}".rstrip()
                if login_uri: 
                    content += f"\nuri:{login_uri}".rstrip()
                content += '\n'  

                if name not in name_to_items:
                    name_to_items[name] = []
                if not username:
                    username = f"«no-username-id{id}»"
                    id += 1
                name_to_items[name].append((username, content))

        
        # json_str = json.dumps(name_to_items, indent=4)
        # print(json_str)
        
        for name, entries_list in name_to_items.items():
            entries_list = list(set(entries_list))
            if len(entries_list) > 1:
                new_dir_path = f"~/.password-store/{name}"
                os.makedirs(new_dir_path, exist_ok=True)
                for username, content in entries_list:
                    entry = f"{name}/{username}"
                    try:
                        subprocess.run(
                            ['pass', 'insert', '-m', entry],
                            input=content.encode('utf-8'),
                            check=True
                        )
                        print(f"Imported: {name} — {username}")
                    except subprocess.CalledProcessError as error:
                        print(f"Error importing {name} — {username}: {error}")
            else:
                content = entries_list[0][1]
                entry = name
                try:
                    subprocess.run(
                        ['pass', 'insert', '-m', entry],
                        input=content.encode('utf-8'),
                        check=True
                    )
                    print(f"Imported: {name} — {username}")
                except subprocess.CalledProcessError as error:
                    print(f"Error importing {name} — {username}: {error}")


if __name__ == "__main__":
    main()
