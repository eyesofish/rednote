# Repository Guidelines

## Project Structure

The root contains `image.png`, a 955 × 742 reference screenshot. The left panel describes the 知光 platform and lists its backend and frontend repository links. The right panel shows a RedNote post about the project. For application changes, follow the corresponding repository link in the left panel. This workspace contains no application source, test suite, or build configuration.

## Working With Images

Keep the `image.png` path when updating the existing reference. For a new screenshot, choose a descriptive lowercase filename such as `zhiguang-project-overview.png` so contributors can identify it from the file listing. Save text-heavy screenshots as PNG to preserve small characters and the punctuation in URLs.

## Local Review

Run `Invoke-Item .\image.png` from the repository root in PowerShell to open the image in the default viewer. Review it at actual size. Check that the Chinese text and both repository links remain legible, then inspect the outer edges of each panel for accidental cropping. If an edit changes the framing or dimensions, describe what the new view is intended to show. There are no build, lint, or automated test commands configured here.

## Commits and Pull Requests

This checkout has no Git history or pull request template. A suggested commit subject is `Refresh the Zhiguang project screenshot`. In the pull request description, identify the file, explain why it changed, and include a before-and-after preview when replacing the image.
