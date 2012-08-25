chrome-app-samples-tagscript
=================

## Use cases:

1. Chromium branch point:
Next script's run will handle it, based on Omaha feed

2. Chrome released to channel:
Next script's run will handle it, based on Omaha feed

3. Samples changed on trunk:
Pull request accepted, no problem

4. Special cases: Samples changed on M?? branches:
Pull request only accepted if it is blocking or very important and branch-specific change. No upstream/merge of changes, never. Script should handle moving the channel tag to the tip of the corresponding branch (step 7 on the script workflow below)

5. Special cases: User branches from a tag, but tag is moved when user submits pull request:
Needs testing. Ideally, PRs, even if the branch was created from a tag, would go either to the appropriate branch (if it is a bug fix specifically on that branch) or to trunk. 

6. Special cases: User branched from a branch that were removed. What happens? Needs testing.

We need to be clear that user branches must only be created from trunk.


## Script workflow:

1. Get Omaha info for a base platform (win?) from http://omahaproxy.appspot.com/all.json. For every channel (dev, beta, stable), get the first digits of version field (eg stable='23')
2. clone remote repository locally
3. run 'git tag -n' to get tags and their annotations (one for each channel - name of corresponding branch is in the annotation)
4. run 'git branch -r' to get branches (one for each active M?? version)
5. if there are versions in Omaha with no corresponding branch, create it from trunk. If there are branches without corresponding Omaha versions, remove the branch.
6. if the current tag->annotation (eg, tag 'stable' is annotated as 'M20') doesn't correspond to the Omaha mapping got on step 1, move the tag to the tip of the branch associated with the version in Omaha (M21, for example) and update the tag's annotation
7. make sure each tag (channel) points to the tip of the corresponding branch, so the tag will always point to the newest branch commits

Tags can be linked directly:
* https://github.com/GoogleChrome/chrome-app-samples/tree/stable
* https://github.com/GoogleChrome/chrome-app-samples/tree/beta
* https://github.com/GoogleChrome/chrome-app-samples/tree/dev

and the corresponding inner links:
* https://github.com/GoogleChrome/chrome-app-samples/tree/dev/helloworld

Also, GitHub automatically creates a link to a ZIP of a tag, allowing directly download links for each channel:
* https://github.com/GoogleChrome/chrome-app-samples/zipball/stable
* https://github.com/GoogleChrome/chrome-app-samples/zipball/beta
* https://github.com/GoogleChrome/chrome-app-samples/zipball/dev

