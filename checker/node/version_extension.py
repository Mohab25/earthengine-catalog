"""Checks for the version extension.

- Catalogs cannot have version information

The remaining is for STAC Collections:

- The version extension schema URL must be 1.0.0
- If any version information, it must have:
  - The STAC version extension
  - A version field
- The version is a string.  The preferred format is MAJOR.MINOR.PATH
  following https://semver.org/, e.g. on Debian Linux:
    dpkg --compare-versions 1.1.2 lt 1.2.2 && echo true
    true
- The deprecated field is an optional bool unless there is a successor-version
  link.  It is okay to have a deprecated: False on other assets, which is the
  default assumed if it not present.
- If a file has deprecated set to true, then the collection must have
  - `[deprecated]` at the end of the title
  - a successor-link
- For each version link must have:
  - an href linking to the STAC Collection for the dataset
  - a title that should be the dataset id being linked to
  - a type that is application/json

- https://github.com/radiantearth/stac-spec/tree/master/extensions
- https://github.com/stac-extensions/version

See also here for a helper library for managing versions:

https://github.com/google/earthengine-catalog/blob/main/catalog/versions.libsonnet

Example version information in python format:
{
  'stac_extensions': [VERSION_URL],
  'version': '2.3.4',
  'deprecated': True,
  'title': 'A title v2.3.4 [deprecated]',
  'links': [
    {'rel': 'latest-version', 'title': 'a/b/2.3.6', 'type': 'application/json'},
    {'rel': 'predecessor-version', 'title': 'a/b/1.9.8', 'type': 'application/json'},
    {'rel': 'successor-version', 'title': 'a/b/2.3.5', 'type': 'application/json'}]}
"""

import re

from typing import Iterator

from checker import stac

EXTENSION_VERSION = '1.0.0'

LINKS = 'links'
REL = 'rel'
VERSION = 'version'

LATEST = 'latest-version'
PREDECESSOR = 'predecessor-version'
SUCCESSOR = 'successor-version'
LINK_TYPES = [LATEST, PREDECESSOR, SUCCESSOR]

DEPRECATED = 'deprecated'
DEPRECATED_TITLE = ' [deprecated]'
TITLE = 'title'
TYPE = 'type'

JSON = 'application/json'


class Check(stac.NodeCheck):
  """Checks the version extension."""
  name = 'version_extension'

  @classmethod
  def run(cls, node: stac.Node) -> Iterator[stac.Issue]:
    extensions = node.stac.get('stac_extensions', [])
    for extension in extensions:
      if not isinstance(extension, str):
        yield cls.new_issue(node, 'Extensions must be a url str')
        return
    extension_list = [ex for ex in extensions if 'github.io/version' in ex]
    extension_url = extension_list[0] if extension_list else None
    has_version_extension = bool(extension_list)

    version_field = node.stac.get(VERSION)
    deprecated = node.stac.get(DEPRECATED)
    has_deprecated = DEPRECATED in node.stac

    links = node.stac.get(LINKS, [])
    if not isinstance(links, list):
      links = []
    version_links = {
        l[REL]: l for l in links
        if isinstance(l, dict) and REL in l and l[REL] in LINK_TYPES}

    if node.type == stac.StacType.CATALOG:
      if has_version_extension:
        yield cls.new_issue(node, 'Catalog must not have the version extension')
      if version_field:
        yield cls.new_issue(node, f'Catalog must not have "{VERSION}"')
      if version_links:
        yield cls.new_issue(node, 'Catalog must not have version links')
      if deprecated is not None:
        yield cls.new_issue(node, f'Catalog must not have "{DEPRECATED}"')
      return

    if not has_version_extension:
      if version_field:
        yield cls.new_issue(
            node, 'Version extension not found, but has version field')
      if has_deprecated:
        yield cls.new_issue(
            node, 'Version extension not found, but has deprecated field')
      if version_links:
        yield cls.new_issue(
            node, 'Version extension not found, but have version links')
      return

    search = re.search(r'v([0-9]+\.[0-9]+\.[0-9]+)', extension_url)
    if search:
      extension_version = search.groups()[0]
      if extension_version != EXTENSION_VERSION:
        yield cls.new_issue(
            node, f'Extension\'s version must be: "{EXTENSION_VERSION}"')
        return

    if not version_field:
      yield cls.new_issue(node, f'Must have "{VERSION}" with the version ext')
    else:
      if not isinstance(version_field, str):
        yield cls.new_issue(node, f'"{VERSION}" must be a str')

    if has_deprecated and not isinstance(deprecated, bool):
      yield cls.new_issue(node, f'"{DEPRECATED}" must be a bool')

    if TITLE in node.stac:
      title = node.stac[TITLE]
      if has_deprecated and deprecated:
        if not title.endswith(DEPRECATED_TITLE):
          yield cls.new_issue(
              node,
              'The title for deprecated assets ' +
              f'must end with "{DEPRECATED_TITLE}"')
      else:
        deprecated_title = DEPRECATED_TITLE.lstrip()
        if title.endswith(deprecated_title):
          yield cls.new_issue(
              node,
              'The title for non-deprecated assets ' +
              f'must not end with "{deprecated_title}"')

    if version_links:
      latest = version_links.get(LATEST)
      predecessor = version_links.get(PREDECESSOR)
      successor = version_links.get(SUCCESSOR)

      if node.id not in [
          'USFS/GTAC/LCMS/v2020-6',
          'USGS/NLCD_RELEASES/2016_REL']:
        if not predecessor and not successor:
          yield cls.new_issue(
              node, f'Must have one of "{PREDECESSOR}" or "{SUCCESSOR}"')

      for link in version_links.values():
        if link.get(TYPE) != JSON:
          yield cls.new_issue(node, f'Link must be of type "{JSON}"')
        if TITLE not in link:
          yield cls.new_issue(node, f'Link must have a "{TITLE}"')

        if deprecated and not latest and not successor:
          yield cls.new_issue(
              node, 'Deprecated assets must have one or both of '
              f'{LATEST} or {SUCCESSOR} links')
        if successor and not deprecated and node.id != 'USFS/GTAC/LCMS/v2020-5':
          yield cls.new_issue(
              node, f'Missing {DEPRECATED} with {SUCCESSOR} link')
