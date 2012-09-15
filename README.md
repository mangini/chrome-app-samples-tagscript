chrome-app-samples-tagscript
=================

## Use cases:

1. Chromium branch point:
Next script's run will handle it, based on Omaha feed

2. Chrome released to channel:
Next script's run will handle it, based on Omaha feed

3. Samples changed on trunk:
Pull request accepted, no problem

4. Special cases: Samples changed on \_\_M?? branches:
Pull request only accepted if it is blocking or very important and branch-specific change. No upstream/merge of changes, never. Script should handle moving the channel branch to the tip of the corresponding version branch (step 7 in the script workflow below)

5. Special cases: User branches from a channel branch, but branch has moved its ref when user submits pull request:
Needs testing. Ideally, PRs from a user branch would go either to the corresponding version branch (if it is a bug fix specifically for that branch) or to trunk. 

6. Special cases: User branched from a version branch that were removed. What happens? Needs testing.

We need to clearly communicate that user branches should almost always be created from trunk.


## Script workflow:

1. [done] Get Omaha info for a base platform (win?) from http://omahaproxy.appspot.com/all.json. For every channel (dev, beta, stable), get the first digits of version field (eg stable='23')
2. [done] clone remote repository locally
3. [done] run 'git branch -l -r' to get branches. Filter \_\_M\d+ as version branches and \_\[^\d\] as channel branches
4. [done] if there are versions in Omaha with no corresponding branch, create them from trunk. If there are branches without corresponding Omaha versions, remove the branch. Same for channels, although that should happen only at the first time.
5. if the current tip of channel branch doesn't correspond to the tip of version branch (eg, branch '\_stable' points to a commit different than '\_\_M21', and supposing that Omaha said that stable is M21 now), update the ref of the channel branch to the tip of the version branch 

Branches can be linked directly:
* https://github.com/GoogleChrome/chrome-app-samples/tree/\_stable
* https://github.com/GoogleChrome/chrome-app-samples/tree/\_beta
* https://github.com/GoogleChrome/chrome-app-samples/tree/\_dev

and the corresponding inner links:
* https://github.com/GoogleChrome/chrome-app-samples/tree/\_dev/helloworld

Also, GitHub automatically creates a link to a ZIP of a branch, allowing directly download links for each channel:
* https://github.com/GoogleChrome/chrome-app-samples/zipball/\_stable
* https://github.com/GoogleChrome/chrome-app-samples/zipball/\_beta
* https://github.com/GoogleChrome/chrome-app-samples/zipball/\_dev

