import sys, json, re, urllib
import subprocess, os, tempfile, shutil
import datetime
import smtplib
import StringIO

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


DEBUG=True
FROM_EMAIL="mangini@chromium.org"
TO_EMAIL="mangini@google.com"

#ACCOUNT="GoogleChrome"
#PROJECT_NAME="chrome-app-samples"
ACCOUNT="mangini"
PROJECT_NAME="mangini-test"
GIT_HOME="https://github.com/%s/%s.git" % (ACCOUNT, PROJECT_NAME)
BASE_URL="https://github.com/%s/%s" % (ACCOUNT, PROJECT_NAME)

OMAHA_URL='http://omahaproxy.appspcot.com/all.json'


DEBUGFILE=StringIO.StringIO()

def _debug(message):
    if (DEBUG):
    	print(message)
    print >>DEBUGFILE, message

def get_omaha_versions():

	try:
		currentVersions = json.loads(urllib.urlopen(OMAHA_URL).read())
	except:
		return {}

	for osObj in currentVersions:
	  if osObj['os'] == 'mac':
	    macVersion = osObj
	    break

	versions = {}

	if macVersion:
		for versionObj in macVersion['versions']: 
			if versionObj['channel']!='canary':
				versions[versionObj['channel']]=versionObj['version'].split('.')[0]
		
		_debug("** Omaha has these versions: %s" % json.dumps(versions))

	return versions


class GitWrapper():
	def __init__(self, path, projectname):
		self.path=path
		self.projectname=projectname
		self.changes=[]
		self.errors=[]

	def execute(self, cmd, execpath=''):
		_debug("Executing: "+cmd)
		pr=subprocess.Popen(cmd, 
			cwd=execpath or self.path+"/"+self.projectname, 
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

		(out, error) = pr.communicate()
		_debug("  stderr: "+error)
		_debug("  stdout: "+out)

		return out


	def clone(self):
		self.execute('git clone %s' % GIT_HOME, self.path)
		self.get_remote_branches()

	def get_tip_of_branch(self, branch):
		branchinfo=self.execute('git show origin/'+branch)
		commit_match=re.compile(r"^commit (\S+)\n").match(branchinfo)
		if commit_match==None: 
 	 		_debug("Branch "+branch+" does not exist yet")
			return None
		last_commit=commit_match.group(1)
		_debug("Branch "+branch+" has last commit "+last_commit)
		return last_commit

	def get_remote_branches(self):
		current_branches=self.execute('git branch -l -r')
		self.channel_branches=re.compile(r"origin/(_[a-z]+)").findall(current_branches)
		self.version_branches=re.compile(r"origin/(__M\d+)").findall(current_branches)

		_debug("** Found these remote branches: %s" % json.dumps(self.version_branches))

	def update_branches(self, version_at_channels_map):

		# create branches for versions that didn't existed before
		for channel in version_at_channels_map:
			version = version_at_channels_map[channel]
			br="__M"+version
			if not br in self.version_branches:
				_debug("** Creating branch: "+br)
				self.changes.append('[+version_branch] Created new version branch: %s' % self.get_branch_url(br))
				self.create_branch(br)
				self.version_branches.append(br)

		# remove branches for versions that are not tracked anymore (make sure these are outside the range of tracked versions)
		for branch in self.version_branches:
			version=re.compile(r"__M(\d+)").match(branch).group(1)
			# if version not mapped to a channel and version is not in the interval of current valid versions, remove it
			if not version in version_at_channels_map.viewvalues() and not (branch>min(self.version_branches) and branch<max(self.version_branches)):
				_debug("** Deleting branch: "+branch)
				self.changes.append('[-version_branch] Removed unused version branch: '+branch)
				self.remove_branch(branch)
				self.version_branches.remove(branch)

		_debug("** branches now should be: %s" % json.dumps(self.version_branches))
		_debug("** versions at channels are: %s" % json.dumps(version_at_channels_map))

		# move channel branches (stable, beta, dev) to point to the appropriate commit
		changed=False
		for channel in version_at_channels_map:
			version = version_at_channels_map[channel]
			version_branch="__M"+version
			channel_branch="_"+channel
			if not channel_branch in self.channel_branches:
				self.create_branch(channel_branch)
				self.changes.append('[+channel_branch] Created new channel branch from trunk: %s' % self.get_branch_url(channel_branch))
				self.pull()
				self.channel_branches.append(channel_branch)

			tip_commit_channel=self.get_tip_of_branch(channel_branch)
			tip_commit_version=self.get_tip_of_branch(version_branch)
			if tip_commit_channel!=tip_commit_version:
				_debug("** Needs to change channel branch "+channel_branch+" from "+tip_commit_channel+" to "+tip_commit_version)
				self.changes.append('[branch_move] Changed branch %s from commit %s to commit %s (version %s)' 
					% ( self.get_branch_url(channel_branch)), tip_commit_channel, tip_commit_version, self.get_branch_url(version_branch) )
				changed=True
				self.update_branch_ref(channel_branch, tip_commit_version, version)

		if changed:
			self.push()


	def get_branch_url(self, branch):
		return '%s %s/tree/%s' % (branch, BASE_URL, branch)

	def update_branch_ref(self, channel_branch, commit, version):
		_debug("** Moving branch "+channel_branch+" to commit "+commit)
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


def sendEmail(content, attachment):
	msg = MIMEMultipart()
	msg['Subject'] = '%s chrome-app-samples branching notification' % str(datetime.date.today())
	msg['From'] = FROM_EMAIL
	msg['To'] = TO_EMAIL
	msg.preamble = content

	msg.attach(MIMEText(attachment, 'text'))
	try:
		s = smtplib.SMTP('localhost')
		s.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
		s.quit()
	except:
		print "ERROR: could not send email: ", sys.exc_info()


def printCollection(title, col):
	str=""
	if len(col)>0:
		str+=title+"\n"
		for item in col:
			str+='* %s\n' % item
	return str


def main(argv=None):
	versions=get_omaha_versions()
	validOmaha='stable' in versions and 'dev' in versions and 'beta' in versions

	temppath = tempfile.mkdtemp()

	try:
		_debug("created %s" % temppath)
		git=GitWrapper(temppath, PROJECT_NAME)
		
		if not validOmaha:
			msg="Invalid Omaha content, versions missing: %s" % json.dumps(versions)
			git.errors.append(msg)
			_debug(msg)
		else: 
			git.clone()
			git.update_branches(versions)

	finally:
		shutil.rmtree(temppath)
		_debug("removed %s" % temppath)

	if len(git.errors)>0 or len(git.changes)>0:
		s='Branches of chrome-app-samples changed accordingly to Chrome versions. Verbose report attached, summary below:\n\n'
		s+=printCollection("Errors:", git.errors)
		s+="\n"
		s+=printCollection("Changes:", git.changes)
		s+='\n(script run at %s)\n' % str(datetime.datetime.now())
		sendEmail(s, DEBUGFILE.getvalue())
	else:
		if DEBUG: print "Nothing changed"

	if len(git.errors)>0:
		return(1)

if __name__ == "__main__":
    sys.exit(main())

