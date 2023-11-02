# -*- coding: utf-8 -*-
"""
Test if vunerable pytphon package is in my project
Requirement : 
    use this command before : 
        conda list --export > requirements.txt
"""
import os
import re    
import requests
#import pandas as pd
url_csv = "https://gist.github.com/masteryoda101/65b55a117fe2ea33735f05024abc92c2/raw/765aa71606c7c6e245aef41581012fa87e38b787/Persistent_Python_Threat_April_August.csv"
path_req = "./requirements.txt"
req = requests.get(url_csv).content
#df_lib = pd.read_csv(io.StringIO(req.decode('utf-8')), sep=";", 
#    low_memory=False)

list_data = re.split(b"[,\n]", req)
list_libs_vul = []
for i_name in range(0, len(list_data), 2):
    list_libs_vul.append(str(list_data[i_name], 'UTF-8'))
    
print("list_libs_vul:")
print(list_libs_vul)

list_libs_project = []
with open(path_req, "rt", encoding="UTF-8") as f:
    for line in f.readlines():
        re_found = re.search("^[\w-]+(?=\=)", line)
        if re_found is not None:
            list_libs_project.append(re_found[0])
print("list_libs_project:")
print(list_libs_project)
s_lib_project_vul = set(list_libs_project).intersection(set(list_libs_vul))
print("list libs vulnerable into project : " , s_lib_project_vul)
if len(s_lib_project_vul) == 0 :
    print("No vulnerable libs found in project : OK")
else:
    raise Exception("WARNING : vulnerable libs into project ! ")

