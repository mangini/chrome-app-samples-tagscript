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
GIT_HOME="git@github.com:%s/%s.git" % (ACCOUNT, PROJECT_NAME)
BASE_URL="https://github.com/%s/%s" % (ACCOUNT, PROJECT_NAME)

OMAHA_URL='http://omahaproxy.appspot.com/all.json'


DEBUGFILE=None

def debug(message):
    if (DEBUG):
    	print(message)
    print >>DEBUGFILE, message

def get_omaha_versions():
	currentVersions = json.loads(urllib.urlopen(OMAHA_URL).read())

	for osObj in currentVersions:
	  if osObj['os'] == 'mac':
	    macVersion = osObj
	    break

	if not macVersion:
		debug("Oops, Omaha JSON does not contain a {os:'mac', ...} object: "+json.dumps(currentVersions))
		exit(1)

	versions = {}

	for versionObj in macVersion['versions']: 
		if versionObj['channel']!='canary':
			versions[versionObj['channel']]=versionObj['version'].split('.')[0]
	
	debug("** Omaha has these versions: %s" % json.dumps(versions))

	return versions


class GitWrapper():
	def __init__(self, path, projectname):
		self.path=path
		self.projectname=projectname
		self.changes=[]

	def execute(self, cmd, execpath=''):
		debug("Executing: "+cmd)
		pr=subprocess.Popen(cmd, 
			cwd=execpath or self.path+"/"+self.projectname, 
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

		(out, error) = pr.communicate()
		debug("  stderr: "+error)
		debug("  stdout: "+out)

		return out


	def clone(self):
		self.execute('git clone %s' % GIT_HOME, self.path)
		self.get_remote_branches()

	def get_tip_of_branch(self, branch):
		branchinfo=self.execute('git show origin/'+branch)
		commit_match=re.compile(r"^commit (\S+)\n").match(branchinfo)
		if commit_match==None: 
 	 		debug("Branch "+branch+" does not exist yet")
			return None
		last_commit=commit_match.group(1)
		debug("Branch "+branch+" has last commit "+last_commit)
		return last_commit

	def get_remote_branches(self):
		current_branches=self.execute('git branch -l -r')
		self.channel_branches=re.compile(r"origin/(_[a-z]+)").findall(current_branches)
		self.version_branches=re.compile(r"origin/(__M\d+)").findall(current_branches)

		debug("** Found these remote branches: %s" % json.dumps(self.version_branches))

	def update_branches(self, version_at_channels_map):

		# create branches for versions that didn't existed before
		for channel in version_at_channels_map:
			version = version_at_channels_map[channel]
			br="__M"+version
			if not br in self.version_branches:
				debug("** Creating branch: "+br)
				self.changes.append('[+version_branch] Created new version branch: %s' % self.get_branch_url(br))
				self.create_branch(br)
				self.version_branches.append(br)

		# remove branches for versions that are not tracked anymore (make sure these are outside the range of tracked versions)
		for branch in self.version_branches:
			version=re.compile(r"__M(\d+)").match(branch).group(1)
			# if version not mapped to a channel and version is not in the interval of current valid versions, remove it
			if not version in version_at_channels_map.viewvalues() and not (branch>min(self.version_branches) and branch<max(self.version_branches)):
				debug("** Deleting branch: "+branch)
				self.changes.append('[-version_branch] Removed unused version branch: '+branch)
				self.remove_branch(branch)
				self.version_branches.remove(branch)

		debug("** branches now should be: %s" % json.dumps(self.version_branches))
		debug("** versions at channels are: %s" % json.dumps(version_at_channels_map))

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
				debug("** Needs to change channel branch "+channel_branch+" from "+tip_commit_channel+" to "+tip_commit_version)
				self.changes.append('[branch_move] Changed branch %s from commit %s to commit %s (version %s)' 
					% ( self.get_branch_url(channel_branch)), tip_commit_channel, tip_commit_version, self.get_branch_url(version_branch) )
				changed=True
				self.update_branch_ref(channel_branch, tip_commit_version, version)

		if changed:
			self.push()


	def get_branch_url(self, branch):
		return '<a href="%s/tree/%s">%s</a>' % (BASE_URL, branch, branch)

	def update_branch_ref(self, channel_branch, commit, version):
		debug("** Moving branch "+channel_branch+" to commit "+commit)
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
	s = smtplib.SMTP('localhost')
	s.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
	s.quit()


def main(argv=None):
	versions=get_omaha_versions()
	if not versions['stable'] or not versions['dev'] or not versions['beta']:
		debug("Invalid Omaha input, versions missing: %s" % json.dumps(versions))
		sys.exit(1)

	temppath = tempfile.mkdtemp()

	DEBUGFILE=StringIO.StringIO()

	try:
		debug("created %s" % temppath)
		git=GitWrapper(temppath, PROJECT_NAME)
		
		git.clone()
		git.update_branches(versions)

	finally:
		shutil.rmtree(temppath)
		debug("removed %s" % temppath)

	if len(git.changes)>0:
		s='Branches of chrome-app-samples changed accordingly to Chrome versions. Verbose report attached, summary below:\n\n'
		for change in git.changes:
			s+='* %s\n' % change
		s+='\n(script run at %s)\n' % str(datetime.datetime.now())
		sendEmail(s, DEBUGFILE.getvalue())
	else:
		print "Nothing changed"


if __name__ == "__main__":
    sys.exit(main())

