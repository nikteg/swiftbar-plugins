"""What github-actions and buildkite share: runs, their failures, and the menu.

A GitHub Actions run and a Buildkite build become the same ``Run``, so both
plugins draw one menu: squircles in the bar grouped by commit, and the same
commit groups, in the same order, in the dropdown. Each source only fetches and parses.

    runs      The Run model, grouping, and the cache of what failed logs said
    github    Runs through ``gh api``
    buildkite Builds through ``bk api``
    menu      The components both plugins' menus are made of
"""
