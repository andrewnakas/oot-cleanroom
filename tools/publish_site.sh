#!/bin/bash
# Publish ../oot/site to gh-pages (site dir is its own git repo on branch gh-pages).
set -e
cd "${1:-/c/Users/andre/n64work/oot/site}"
rm -f soh.data
touch .nojekyll
git add -A
git commit -qm "${2:-Site update}

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" || true
git push -q -f origin gh-pages
echo pushed
