"""Collect and sort version strings."""

import re

RE_SEMVER = re.compile(r'^v?V?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?([\w.+-]*)$')


def semvers(names):
    """Parse versions into integers and convert non-integer meta indicators into integers with ord().

    Each return list item has an indicator as the first item. 0 for valid versions and 1 for invalid. Can be used to
    sort non-version names (e.g. master, feature_branch, etc) after valid versions. No sorting is done in this function
    though.

    Read multi_sort() docstring for reasoning behind inverted integers in version_ints variable.

    :param iter names: List of strings representing versions/tags/branches.

    :return: List of parsed versions. E.g. v1.10.0b3 -> [0, 1, 10, 0, ord('b'), ord('3')]
    :rtype: list
    """
    matches = [(RE_SEMVER.findall(n) or [[]])[0] for n in names]
    max_len_ints = 0
    max_len_str = 0

    # Get max lens for padding.
    for match in (m for m in matches if m):
        max_len_ints = len(match)  # Never changes.
        max_len_str = max(max_len_str, len(match[-1]))
    if not max_len_ints:
        return matches  # Nothing to do, all empty.
    invalid_template = [1] + [0] * (max_len_ints + max_len_str - 1)

    # Parse.
    exploded_semver = list()
    for match in matches:
        if not match:
            exploded_semver.append(invalid_template[:])
            continue
        version_ints = [-int(i or 0) for i in match[:-1]]
        ints_of_str = [ord(i) for i in match[-1]] + [0] * (max_len_str - len(match[-1]))
        exploded_semver.append([0] + version_ints + ints_of_str)

    return exploded_semver


def multi_sort(remotes, sort):
    """Sort `remotes` in place. Allows sorting by multiple conditions.

    This is needed because Python 3 no longer supports sorting lists of multiple types. Sort keys must all be of the
    same type.

    Problem: the user expects versions to be sorted latest first and chronological to be most recent first (when viewing
    the HTML documentation), yet expects alphabetical sorting to be A before Z.
    Solution: invert integers (dates and parsed versions).

    :param iter remotes: List of dicts from Versions().remotes.
    :param iter sort: What to sort by. May be one or more of: alpha, chrono, semver
    """
    exploded_alpha = list()
    exploded_semver = list()

    # Convert name to int if alpha is in sort.
    if 'alpha' in sort:
        alpha_max_len = max(len(r['name']) for r in remotes)
        for name in (r['name'] for r in remotes):
            exploded_alpha.append([ord(i) for i in name] + [0] * (alpha_max_len - len(name)))

    # Parse versions if semver is in sort.
    if 'semver' in sort:
        exploded_semver = semvers(r['name'] for r in remotes)

    # Build sort_mapping dict.
    sort_mapping = dict()
    for i, remote in enumerate(remotes):
        key = list()
        for sort_by in sort:
            if sort_by == 'alpha':
                key.extend(exploded_alpha[i])
            elif sort_by == 'chrono':
                key.append(-remote['date'])
            elif sort_by == 'semver':
                key.extend(exploded_semver[i])
        sort_mapping[id(remote)] = key

    # Sort.
    remotes.sort(key=lambda k: sort_mapping.get(id(k)))


class Versions(object):
    """Iterable class that holds all versions and handles sorting and filtering. To be fed into Sphinx's Jinja2 env.

    URLs are just '.' initially. Set after instantiation by another function elsewhere. Will be relative URL path.

    :ivar iter remotes: List of dicts for every branch/tag. Dict keys are: sha, name, kind, date, and url.
    """

    def __init__(self, remotes, sort=None, prioritize=None, invert=False):
        """Constructor.

        :param iter remotes: Output of routines.gather_git_info(). Converted to list of dicts as instance variable.
        :param iter sort: List of strings (order matters) to sort remotes by. Strings may be: alpha, chrono, semver
        :param str prioritize: May be "branches" or "tags". Groups either before the other. Maintains order otherwise.
        :param bool invert: Invert sorted/grouped remotes at the end of processing.
        """
        self.remotes = [dict(sha=r[0], name=r[1], kind=r[2], date=r[3], url='.') for r in remotes]

        # Sort one or more times.
        if sort:
            multi_sort(self.remotes, [s.strip().lower() for s in sort])

        # Prioritize.
        if prioritize == 'branches':
            self.remotes.sort(key=lambda r: 1 if r['kind'] == 'tags' else 0)
        elif prioritize == 'tags':
            self.remotes.sort(key=lambda r: 0 if r['kind'] == 'tags' else 1)

        # Invert.
        if invert:
            self.remotes.reverse()

    def __iter__(self):
        """Yield name and urls of branches and tags."""
        for remote in self.remotes:
            yield remote['name'], remote['url']

    @property
    def branches(self):
        """Yield (name and urls) only branches."""
        for remote in self.remotes:
            if remote['kind'] == 'heads':
                yield remote['name'], remote['url']

    @property
    def tags(self):
        """Yield (name and urls) only tags."""
        for remote in self.remotes:
            if remote['kind'] == 'tags':
                yield remote['name'], remote['url']
