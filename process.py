import sys, json, re, urllib
import subprocess, os, tempfile, shutil

PROJECT_NAME="mangini-test"
GIT_HOME="git@github.com:mangini/%s.git" % PROJECT_NAME

#PROJECT_NAME="chrome-app-samples"
#GIT_HOME="git@github.com:GoogleChrome/%s.git" % PROJECT_NAME

def get_omaha_versions():
	url = 'http://omahaproxy.appspot.com/all.json'
	currentVersions = json.loads(urllib.urlopen(url).read())

	for osObj in currentVersions:
	  if osObj['os'] == 'mac':
	    macVersion = osObj
	    break

	if not macVersion:
		print("Oops, JSON does not contain a {os:'mac', ...} object: "+json.dumps(currentVersions))
		exit(1)

	versions = {}

	for versionObj in macVersion['versions']: 
		versions[versionObj['channel']]=versionObj['version'].split('.')[0];
	
	return versions

class GitWrapper():
	def __init__(self, path, projectname):
		self.path=path
		self.projectname=projectname

	def execute(self, cmd, execpath=''):
		pr=subprocess.Popen(cmd, 
			cwd=execpath or self.path+"/"+self.projectname, 
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

		(out, error) = pr.communicate()

		if (error): 
			print "git error: %s" % error
			exit(1)

		return out


	def clone(self):
		self.execute('git clone %s' % GIT_HOME, self.path)

	def check_branches(self, channel_version):
		branches=self.execute('git branch -l')
		for channel in channel_version:
			version = channel_version[channel]
			# search for __M?? in the current branches:
			if (not re.search(r'__%s' % version, branches)):
				self.create_branch("__"+version)

	def create_branch(self, branch_name):
		self.execute('git branch %s' % branch_name)
		result=self.execute('git push origin %s' % branch_name)
		print "creating branch "+branch_name+": "+result
	    
	def list_tags(self):
		self.execute('git tag -n')


def main(argv=None):
	versions=get_omaha_versions()
	temppath = tempfile.mkdtemp()

	try:
		print "created %s" % temppath

		git=GitWrapper(temppath, PROJECT_NAME)
		
		git.clone()
		git.check_branches(versions)

	finally:
		shutil.rmtree(temppath);
		print "removed %s" % temppath

	print(json.dumps(versions))


if __name__ == "__main__":
    sys.exit(main())

