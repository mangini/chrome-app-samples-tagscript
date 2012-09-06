import sys, json, re, urllib
import subprocess, os, tempfile, shutil

DEBUG=True
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
		if versionObj['channel']!='canary':
			versions[versionObj['channel']]=versionObj['version'].split('.')[0];
	
	if DEBUG: 
		print("** Omaha has these versions: %s" % json.dumps(versions))

	return versions

class GitWrapper():
	def __init__(self, path, projectname):
		self.path=path
		self.projectname=projectname

	def execute(self, cmd, execpath=''):
		if DEBUG: print("Executing: "+cmd)
		pr=subprocess.Popen(cmd, 
			cwd=execpath or self.path+"/"+self.projectname, 
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

		(out, error) = pr.communicate()
		if DEBUG: 
			print("  stderr: "+error)
			print("  stdout: "+out)

		return out


	def clone(self):
		self.execute('git clone %s' % GIT_HOME, self.path)
		self.get_remote_branches()

	def get_tip_of_branch(self, branch):
		branchinfo=self.execute('git show origin/'+branch)
		commit_match=re.compile(r"^commit (\S+)\n").match(branchinfo)
		if commit_match==None: 
 	 		if DEBUG: print("Branch "+branch+" does not exist yet")
			return None
		last_commit=commit_match.group(1)
		if DEBUG: print("Branch "+branch+" has last commit "+last_commit)
		return last_commit

	def get_remote_branches(self):
		current_branches=self.execute('git branch -l -r')
		self.channel_branches=re.compile(r"origin/(__[a-z]+)").findall(current_branches)
		self.version_branches=re.compile(r"origin/(__M\d+)").findall(current_branches)

		if DEBUG: print("** Found these remote branches: %s" % json.dumps(self.version_branches))

	def update_branches(self, version_at_channels_map):

		# create branches for versions that didn't existed before
		for channel in version_at_channels_map:
			version = version_at_channels_map[channel]
			br="__M"+version
			if not br in self.version_branches:
				if DEBUG: print("** Creating branch: "+br)
				self.create_branch(br)
				self.version_branches.append(br)

		# remove branches for versions that are not tracked anymore (make sure these are outside the range of tracked versions)
		for branch in self.version_branches:
			version=re.compile(r"__M(\d+)").match(branch).group(1)
			# if version not mapped to a channel and version is not in the interval of current valid versions, remove it
			if not version in version_at_channels_map.viewvalues() and not (branch>min(self.version_branches) and branch<max(self.version_branches)):
				if DEBUG: print("** Deleting branch: "+branch)
				self.remove_branch(branch)
				self.version_branches.remove(branch)

		if DEBUG: print("** branches now should be: %s" % json.dumps(self.version_branches))
		if DEBUG: print("** versions at channels are: %s" % json.dumps(version_at_channels_map))

		# move channel branches (stable, beta, dev) to point to the appropriate commit
		changed=False
		for channel in version_at_channels_map:
			version = version_at_channels_map[channel]
			version_branch="__M"+version
			channel_branch="__"+channel
			if not channel_branch in self.channel_branches:
				self.create_branch(channel_branch)
				self.pull()
				self.channel_branches.append(channel_branch)

			tip_commit_channel=self.get_tip_of_branch(channel_branch)
			tip_commit_version=self.get_tip_of_branch(version_branch)
			if tip_commit_channel!=tip_commit_version:
				print("** Needs to change channel branch "+channel_branch+" from "+tip_commit_channel+" to "+tip_commit_version)
				changed=True
				self.update_branch_ref(channel_branch, tip_commit_version, version)

		if changed:
			self.push()


	def update_branch_ref(self, channel_branch, commit, version):
		if DEBUG: print("** Moving branch "+channel_branch+" to commit "+commit)
		message='"moving channel '+channel_branch+' to version '+ version+'"'
		self.execute('git update-ref -m '+message+' refs/heads/'+channel_branch+' '+commit)

	def push(self):
		self.execute('git push -f')

	def pull(self):
		self.execute('git pull')
	    
	def remove_branch(self, branch_name):
		self.execute('git branch -D -r origin/%s' % branch_name)
		result=self.execute('git push origin :%s' % branch_name)
	    
	def create_branch(self, branch_name):
		self.execute('git branch %s' % branch_name)
		result=self.execute('git push origin %s' % branch_name)


def main(argv=None):
	versions=get_omaha_versions()
	if not versions['stable'] or not versions['dev'] or not versions['beta']:
		print("Invalid Omaha input, versions missing: %s" % json.dumps(versions))
		sys.exit(1)

	temppath = tempfile.mkdtemp()

	try:
		if DEBUG: print "created %s" % temppath

		git=GitWrapper(temppath, PROJECT_NAME)
		
		git.clone()
		git.update_branches(versions)

	finally:
		shutil.rmtree(temppath);
		if DEBUG: print "removed %s" % temppath



if __name__ == "__main__":
    sys.exit(main())

