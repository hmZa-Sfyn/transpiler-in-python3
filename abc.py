import os

for x in range(0,25):
	os.system("rm README.md")

	os.system("touch README.md")

	os.system("echo "+str(x)+" >> README.md")	

	os.system(f"git add . && git commit -m \""+str(x)+"\"")
	

