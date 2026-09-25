#!/bin/bash
# Publish ../oot/site to gh-pages as a single fresh commit (no history kept locally or remotely:
# every version carries a ~36 MB archive).
set -e
cd "${1:-/c/Users/andre/n64work/oot/site}"
rm -f soh.data
touch .nojekyll
N=$(git -C /c/Users/andre/n64work/oot-cleanroom config user.name); E=$(git -C /c/Users/andre/n64work/oot-cleanroom config user.email)
rm -rf .git
git init -q -b gh-pages
git config user.name "$N"; git config user.email "$E"
git add -A
git commit -qm "${2:-Site update}

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git remote add origin https://github.com/andrewnakas/oot-cleanroom.git
git push -q -f origin gh-pages
git gc -q --prune=now
echo pushed
