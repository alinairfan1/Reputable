import os
import sys
from github import Github, Auth
from dotenv import load_dotenv
from feature_config import extract_features_from_pygithub

load_dotenv(os.path.join(os.path.dirname(__file__), "backend/.env"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
g = Github(auth=Auth.Token(GITHUB_TOKEN)) if GITHUB_TOKEN else Github()

repo = g.get_repo("theopenco/llmgateway")
contents = repo.get_contents("")
root_keys = {item.name.lower(): item.type for item in contents}

print("Keys:", root_keys)
print("Intersection:", {"dockerfile", "docker-compose.yml", "docker-compose.yaml"} & root_keys.keys())

features = extract_features_from_pygithub(repo)
print("Features:", features)
