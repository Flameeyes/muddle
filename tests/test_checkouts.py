#! /usr/bin/env python
"""Test checkout support.

Give a single argument (one of 'git', 'bzr' or 'svn') to do tests for a
particular version control system. That VCS must be installed on the
machine you are running this on. For example::

    $ ./test_checkouts.py git

Give a set of commands starting with 'muddle' to run a muddle command,
just as if you were running the muddle command line program itself. For
example::

    $ ./test_checkouts.py muddle help query

The normal variants on 'help', '-help', etc. will probably work to
give this text...
"""

import os
import shutil
import subprocess
import sys

this_file = os.path.abspath(__file__)
this_dir = os.path.split(this_file)[0]
parent_dir = os.path.split(this_dir)[0]

try:
    import muddled.cmdline
    from muddled.utils import Error, Failure
except ImportError:
    # Try one level up
    sys.path.insert(0,parent_dir)
    import muddled.cmdline
    from muddled.utils import Error, Failure

MUDDLE_BINARY = '%s muddle'%this_file

# Make up for not necessarily having a PYTHONPATH that helps
# Assume the location of muddle_patch.py relative to ourselves
MUDDLE_PATCH_COMMAND = '%s/muddle_patch.py'%(parent_dir)

MUDDLE_MAKEFILE = """\
# Trivial muddle makefile
all:
\t@echo Make all for $(MUDDLE_LABEL)

config:
\t@echo Make configure for $(MUDDLE_LABEL)

install:
\t@echo Make install for $(MUDDLE_LABEL)

clean:
\t@echo Make clean for $(MUDDLE_LABEL)

distclean:
\t@echo Make distclean for $(MUDDLE_LABEL)

.PHONY: all config install clean distclean
"""

CHECKOUT_BUILD = """ \
# Test build for testing checkouts
# Does not test 'repo_rel', since git does not support cloning a "bit" of a
# repository. Testing that will have to wait for subversion testing (!).

import muddled.checkouts.simple
import muddled.checkouts.twolevel
import muddled.checkouts.multilevel

def describe_to(builder):
    builder.build_name = 'checkout_test'

    # checkout1
    # Simple, <repo>/<checkout> -> src/<checkout>
    muddled.checkouts.simple.relative(builder,
                                      co_name='checkout1')

    # checkout2
    # twolevel, <repo>/twolevel/<checkout> -> src/twolevel/<checkout>
    muddled.checkouts.twolevel.relative(builder,
                                        co_dir='twolevel',
                                        co_name='checkout2')

    # checkout3
    # Multilevel, <repo>/multilevel/inner/<checkout> -> src/multilevel/inner/<checkout>
    muddled.checkouts.multilevel.relative(builder,
                                          co_dir='multilevel/inner/checkout3',
                                          co_name='alice')
"""


def normalise(dir):
    dir = os.path.expanduser(dir)
    dir = os.path.abspath(dir)
    return dir

class Directory(object):
    """A class to facilitate pushd/popd behaviour

    It is intended for use with 'with', as in::

        with Directory('~'):
            print 'My home directory contains'
            print ' ',' '.join(os.listdir('.'))
    """
    def __init__(self, where, verbose=True):
        self.start = normalise(os.getcwd())
        self.where = normalise(where)
        self.verbose = verbose
        os.chdir(self.where)
        if verbose:
            print '++ pushd to %s'%self.where

    def close(self):
        os.chdir(self.start)
        if self.verbose:
            print '++ popd to %s'%self.start

    def __enter__(self):
        return self

    def __exit__(self, etype, value, tb):
        if tb is None:
            # No exception, so just finish normally
            self.close()
        else:
            # An exception occurred, so do any tidying up necessary
            if self.verbose:
                print '** Oops, an exception occurred - %s tidying up'%self.__class__.__name__
            # well, there isn't anything special to do, really
            self.close()
            if self.verbose:
                print '** ----------------------------------------------------------------------'
            # And allow the exception to be re-raised
            return False

class NewDirectory(Directory):
    """A pushd/popd directory that gets created first.

    It is an Error if the directory already exists.
    """
    def __init__(self, where, verbose=True):
        where = normalise(where)
        if os.path.exists(where):
            raise Error('Directory %s already exists'%where)
        if verbose:
            print '++ mkdir %s'%where
        os.makedirs(where)
        super(NewDirectory, self).__init__(where, verbose)

class TransientDirectory(NewDirectory):
    """A pushd/popd directory that gets created first and deleted afterwards

    If 'keep_on_error' is True, then the directory will not be deleted
    if an exception occurs in its 'with' clause.

    It is an Error if the directory already exists.
    """
    def __init__(self, where, keep_on_error=False, verbose=True):
        self.rmtree_on_error = not keep_on_error
        super(TransientDirectory, self).__init__(where, verbose)

    def close(self, delete_tree):
        super(NewDirectory, self).close()
        if delete_tree:
            if self.verbose:
                # The extra space after 'rmtree' is so the directory name
                # left aligns with a previous 'popd to' message
                print '++ rmtree  %s'%self.where
            shutil.rmtree(self.where)

    def __exit__(self, etype, value, tb):
        if tb is None:
            # No exception, so just finish normally
            self.close(True)
        else:
            # An exception occurred, so do any tidying up necessary
            if self.verbose:
                print '** Oops, an exception occurred - %s tidying up'%self.__class__.__name__
            # but don't delete the tree if we've been asked not to
            self.close(self.rmtree_on_error)
            if self.verbose:
                print '** ----------------------------------------------------------------------'
            # And allow the exception to be re-raised
            return False

class ShellError(Error):
    def __init__(self, cmd, retcode):
        msg = "Shell command '%s' failed with retcode %d"%(cmd, retcode)
        super(Error, self).__init__(msg)
        self.retcode=retcode

def shell(cmd, verbose=True):
    """Run a command in the shell
    """
    print '>> %s'%cmd
    retcode = subprocess.call(cmd, shell=True)
    if retcode:
        raise ShellError(cmd, retcode)

def muddle(args, verbose=True):
    """Pretend to be muddle

    I already know it's going to be a pain remembering that the first
    argument is a list of words...
    """
    if verbose:
        print '++ muddle %s'%(' '.join(args))
    muddled.cmdline.cmdline(args, MUDDLE_BINARY)

def git(cmd, verbose=True):
    """Run a git command
    """
    shell('%s %s'%('git',cmd), verbose)

def bzr(cmd, verbose=True):
    """Run a bazaar command
    """
    shell('%s %s'%('bzr',cmd), verbose)

def svn(cmd, verbose=True):
    """Run a subversion command
    """
    shell('%s %s'%('svn',cmd), verbose)

def cat(filename):
    """Print out the contents of a file.
    """
    with open(filename) as fd:
        print '++ cat %s'%filename
        print '='*40
        for line in fd.readlines():
            print line.rstrip()
        print '='*40

def touch(filename, content=None, verbose=True):
    """Create a new file, and optionally give it content.
    """
    if verbose:
        print '++ touch %s'%filename
    with open(filename, 'w') as fd:
        if content:
            fd.write(content)

def check_files(paths, verbose=True):
    """Given a list of paths, check they all exist.
    """
    if verbose:
        print '++ Checking files exist'
    for name in paths:
        if os.path.exists(name):
            if verbose:
                print '  -- %s'%name
        else:
            raise Error('File %s does not exist'%name)
    if verbose:
        print '++ All named files exist'

def check_specific_files_in_this_dir(names, verbose=True):
    """Given a list of filenames, check they are the only files
    in the current directory
    """
    wanted_files = set(names)
    actual_files = set(os.listdir('.'))

    if verbose:
        print '++ Checking only specific files exist in this directory'
        print '++ Wanted files are: %s'%(', '.join(wanted_files))

    if wanted_files != actual_files:
        text = ''
        missing_files = wanted_files - actual_files
        if missing_files:
            text += '    Missing: %s\n'%', '.join(missing_files)
        extra_files = actual_files - wanted_files
        if extra_files:
            text += '    Extra: %s\n'%', '.join(extra_files)
        raise Error('Required files are not matched\n%s'%text)
    else:
        if verbose:
            print '++ Only the requested files exist'

def check_nosuch_files(paths, verbose=True):
    """Given a list of paths, check they do not exist.
    """
    if verbose:
        print '++ Checking files do not exist'
    for name in paths:
        if os.path.exists(name):
            raise Error('File %s exists'%name)
        else:
            if verbose:
                print '  -- %s'%name
    if verbose:
        print '++ All named files do not exist'

def banner(text):
    delim = '*' * (len(text)+4)
    print delim
    print '* %s *'%text
    print delim

def test_svn_simple_build():
    """Bootstrap a muddle build tree.
    """
    root_dir = normalise(os.getcwd())

    with NewDirectory('repo'):
        for name in ('main', 'versions'):
            shell('svnadmin create %s'%name)

        print 'Repositories are:', ' '.join(os.listdir('.'))

    root_repo = 'file://' + os.path.join(root_dir, 'repo', 'main')
    versions_repo = 'file://' + os.path.join(root_dir, 'repo', 'versions')
    with NewDirectory('test_build1'):
        banner('Bootstrapping simple build')
        muddle(['bootstrap', 'svn+%s'%root_repo, 'test_build'])
        cat('src/builds/01.py')

        # But, of course, we don't keep the versions/ directory in the same
        # repository (lest things get very confused)
        touch('.muddle/VersionsRepository', 'svn+%s\n'%versions_repo)
        with Directory('versions'):
            touch('fred.stamp',
                  '# A comment\n# Another comment\n')
            svn('import . %s -m "Initial import"'%versions_repo)

        # Is the next really the best we can do?
        shell('rm -rf versions')
        svn('checkout %s'%versions_repo)

        with Directory('src'):
            with Directory('builds'):
                svn('import . %s/builds -m "Initial import"'%root_repo)

            # Is the next really the best we can do?
            shell('rm -rf builds')
            svn('checkout %s/builds'%root_repo)

        banner('Stamping simple build')
        muddle(['stamp', 'version'])
        with Directory('versions'):
            svn('add test_build.stamp')
            svn('commit -m "A proper stamp file"')
            cat('test_build.stamp')

    # We should be able to check everything out from the repository
    with NewDirectory('test_build2'):
        banner('Building from init')
        muddle(['init', 'svn+%s'%root_repo, 'builds/01.py'])
        muddle(['checkout','_all'])

    # We should be able to recreate our state from the stamp file...
    with NewDirectory('test_build3'):
        banner('Unstamping simple build')
        # Note that we do not ask for 'versions/test_build.stamp', since
        # our repository corresponds to this versions/ directory as a whole...
        muddle(['unstamp', 'svn+%s'%versions_repo, 'test_build.stamp'])

def test_git_simple_build():
    """Bootstrap a muddle build tree.
    """
    root_dir = normalise(os.getcwd())

    with NewDirectory('repo'):
        for name in ('builds', 'versions'):
            with NewDirectory(name):
                git('init --bare')

        print 'Repositories are:', ' '.join(os.listdir('.'))

    root_repo = 'file://' + os.path.join(root_dir, 'repo')
    with NewDirectory('test_build1'):
        banner('Bootstrapping simple build')
        muddle(['bootstrap', 'git+%s'%root_repo, 'test_build'])
        cat('src/builds/01.py')

        with Directory('versions'):
            touch('fred.stamp',
                  '# A comment\n# Another comment\n')
            git('add fred.stamp')
            git('commit -m "New stamp file"')
            git('push %s/versions HEAD'%root_repo)

        with Directory('src/builds'):
            git('commit -m "New build"')
            git('push %s/builds HEAD'%root_repo)

        banner('Stamping simple build')
        muddle(['stamp', 'version'])
        with Directory('versions'):
            git('add test_build.stamp')
            git('commit -m "A proper stamp file"')
            cat('test_build.stamp')

        # We should be able to use muddle to push the stamp file
        muddle(['stamp', 'push'])

    # We should be able to check everything out from the repository
    with NewDirectory('test_build2'):
        banner('Building from init')
        muddle(['init', 'git+%s'%root_repo, 'builds/01.py'])
        muddle(['checkout','_all'])

    # We should be able to recreate our state from the stamp file...
    with NewDirectory('test_build3'):
        banner('Unstamping simple build')
        muddle(['unstamp', 'git+%s'%root_repo, 'versions/test_build.stamp'])

def test_bzr_simple_build():
    """Bootstrap a muddle build tree.
    """
    root_dir = normalise(os.getcwd())

    with NewDirectory('repo'):
        for name in ('builds', 'versions'):
            with NewDirectory(name):
                bzr('init')

        print 'Repositories are:', ' '.join(os.listdir('.'))

    root_repo = 'file://' + os.path.join(root_dir, 'repo')
    with NewDirectory('test_build1'):
        banner('Bootstrapping simple build')
        muddle(['bootstrap', 'bzr+%s'%root_repo, 'test_build'])
        cat('src/builds/01.py')

        with Directory('versions'):
            touch('fred.stamp',
                  '# A comment\n# Another comment\n')
            bzr('add fred.stamp')
            bzr('commit -m "New stamp file"')
            bzr('push %s/versions'%root_repo)

        with Directory('src/builds'):
            bzr('commit -m "New build"')
            bzr('push %s/builds'%root_repo)

        banner('Stamping simple build')
        muddle(['reparent', 'builds'])  # Not sure why we need to do this
        muddle(['stamp', 'version'])
        with Directory('versions'):
            bzr('add test_build.stamp')
            bzr('commit -m "A proper stamp file"')
            cat('test_build.stamp')

        # We should be able to use muddle to push the stamp file
        muddle(['stamp', 'push'])

    # We should be able to check everything out from the repository
    with NewDirectory('test_build2'):
        banner('Building from init')
        muddle(['init', 'bzr+%s'%root_repo, 'builds/01.py'])
        muddle(['checkout','_all'])

    # We should be able to recreate our state from the stamp file...
    with NewDirectory('test_build3'):
        banner('Unstamping simple build')
        muddle(['unstamp', 'bzr+%s'%root_repo, 'versions/test_build.stamp'])

def setup_git_checkout_repositories():
    """Set up our testing repositories in the current directory.
    """
    banner('Setting up checkout repos')
    with NewDirectory('repo'):
        # The standards
        for name in ('builds', 'versions'):
            with NewDirectory(name):
                git('init --bare')

        # Single level checkouts
        with NewDirectory('checkout1'):
            git('init --bare')

        # Two-level checkouts
        with NewDirectory('twolevel'):
            with NewDirectory('checkout2'):
                git('init --bare')

        # Multilevel checkouts
        with NewDirectory('multilevel'):
            with NewDirectory('inner'):
                with NewDirectory('checkout3'):
                    git('init --bare')

def test_git_checkout_build():
    """Test single, twolevel and multilevel checkouts.

    Relies on setup_git_checkout_repositories() having been called.
    """
    root_dir = normalise(os.getcwd())

    root_repo = 'file://' + os.path.join(root_dir, 'repo')
    with NewDirectory('test_build1'):
        banner('Bootstrapping checkout build')
        muddle(['bootstrap', 'git+%s'%root_repo, 'test_build'])
        cat('src/builds/01.py')

        banner('Setting up src/')
        with Directory('src'):
            with Directory('builds'):
                touch('01.py', CHECKOUT_BUILD)
                git('add 01.py')
                git('commit -m "New build"')
                git('push %s/builds HEAD'%root_repo)

            with NewDirectory('checkout1'):
                touch('Makefile.muddle', MUDDLE_MAKEFILE)
                git('init')
                git('add Makefile.muddle')
                git('commit -m "Add muddle makefile"')
                git('push %s/checkout1 HEAD'%root_repo)
                muddle(['assert', 'checkout:checkout1/checked_out'])

            with NewDirectory('twolevel'):
                with NewDirectory('checkout2'):
                    touch('Makefile.muddle', MUDDLE_MAKEFILE)
                    git('init')
                    git('add Makefile.muddle')
                    git('commit -m "Add muddle makefile"')
                    git('push %s/twolevel/checkout2 HEAD'%root_repo)
                    muddle(['assert', 'checkout:checkout2/checked_out'])

            with NewDirectory('multilevel'):
                with NewDirectory('inner'):
                    with NewDirectory('checkout3'):
                        touch('Makefile.muddle', MUDDLE_MAKEFILE)
                        git('init')
                        git('add Makefile.muddle')
                        git('commit -m "Add muddle makefile"')
                        git('push %s/multilevel/inner/checkout3 HEAD'%root_repo)
                        muddle(['assert', 'checkout:alice/checked_out'])

        banner('Stamping checkout build')
        muddle(['stamp', 'version'])
        with Directory('versions'):
            git('add checkout_test.stamp')
            git('commit -m "A stamp file"')
            git('push %s/versions HEAD'%root_repo)
            cat('checkout_test.stamp')

        # We should be able to use muddle to push the stamp file
        muddle(['stamp', 'push'])

    # We should be able to check everything out from the repository
    with NewDirectory('test_build2'):
        banner('Building checkout build from init')
        muddle(['init', 'git+%s'%root_repo, 'builds/01.py'])
        muddle(['checkout','_all'])

        check_files(['src/builds/01.py',
                     'src/checkout1/Makefile.muddle',
                     'src/twolevel/checkout2/Makefile.muddle',
                     'src/multilevel/inner/checkout3/Makefile.muddle',
                     ])

    # We should be able to recreate our state from the stamp file...
    with NewDirectory('test_build3'):
        banner('Unstamping checkout build')
        muddle(['unstamp', 'git+%s'%root_repo, 'versions/checkout_test.stamp'])

        check_files(['src/builds/01.py',
                     'versions/checkout_test.stamp',
                     'src/checkout1/Makefile.muddle',
                     'src/twolevel/checkout2/Makefile.muddle',
                     'src/multilevel/inner/checkout3/Makefile.muddle',
                     ])

def setup_bzr_checkout_repositories():
    """Set up our testing repositories in the current directory.
    """
    banner('Setting up checkout repos')
    with NewDirectory('repo'):
        # The standards
        for name in ('builds', 'versions'):
            with NewDirectory(name):
                bzr('init')

        # Single level checkouts
        with NewDirectory('checkout1'):
            bzr('init')

        # Two-level checkouts
        with NewDirectory('twolevel'):
            with NewDirectory('checkout2'):
                bzr('init')

        # Multilevel checkouts
        with NewDirectory('multilevel'):
            with NewDirectory('inner'):
                with NewDirectory('checkout3'):
                    bzr('init')

def test_bzr_checkout_build():
    """Test single, twolevel and multilevel checkouts.

    Relies on setup_bzr_checkout_repositories() having been called.
    """
    root_dir = normalise(os.getcwd())

    root_repo = 'file://' + os.path.join(root_dir, 'repo')
    with NewDirectory('test_build1'):
        banner('Bootstrapping checkout build')
        muddle(['bootstrap', 'bzr+%s'%root_repo, 'test_build'])
        cat('src/builds/01.py')

        banner('Setting up src/')
        with Directory('src'):
            with Directory('builds'):
                touch('01.py', CHECKOUT_BUILD)
                bzr('add 01.py')
                bzr('commit -m "New build"')
                bzr('push %s/builds'%root_repo)

            with NewDirectory('checkout1'):
                touch('Makefile.muddle', MUDDLE_MAKEFILE)
                bzr('init')
                bzr('add Makefile.muddle')
                bzr('commit -m "Add muddle makefile"')
                bzr('push %s/checkout1'%root_repo)
                muddle(['assert', 'checkout:checkout1/checked_out'])

            with NewDirectory('twolevel'):
                with NewDirectory('checkout2'):
                    touch('Makefile.muddle', MUDDLE_MAKEFILE)
                    bzr('init')
                    bzr('add Makefile.muddle')
                    bzr('commit -m "Add muddle makefile"')
                    bzr('push %s/twolevel/checkout2'%root_repo)
                    muddle(['assert', 'checkout:checkout2/checked_out'])

            with NewDirectory('multilevel'):
                with NewDirectory('inner'):
                    with NewDirectory('checkout3'):
                        touch('Makefile.muddle', MUDDLE_MAKEFILE)
                        bzr('init')
                        bzr('add Makefile.muddle')
                        bzr('commit -m "Add muddle makefile"')
                        bzr('push %s/multilevel/inner/checkout3'%root_repo)
                        muddle(['assert', 'checkout:alice/checked_out'])

        banner('Stamping checkout build')
        muddle(['reparent', '_all'])  # Probably need to do this?
        muddle(['stamp', 'version'])
        with Directory('versions'):
            bzr('add checkout_test.stamp')
            bzr('commit -m "A stamp file"')
            bzr('push %s/versions'%root_repo)
            cat('checkout_test.stamp')

        # We should be able to use muddle to push the stamp file
        muddle(['stamp', 'push'])

    # We should be able to check everything out from the repository
    with NewDirectory('test_build2'):
        banner('Building checkout build from init')
        muddle(['init', 'bzr+%s'%root_repo, 'builds/01.py'])
        muddle(['checkout','_all'])

        check_files(['src/builds/01.py',
                     'src/checkout1/Makefile.muddle',
                     'src/twolevel/checkout2/Makefile.muddle',
                     'src/multilevel/inner/checkout3/Makefile.muddle',
                     ])

    # We should be able to recreate our state from the stamp file...
    with NewDirectory('test_build3'):
        banner('Unstamping checkout build')
        muddle(['unstamp', 'bzr+%s'%root_repo, 'versions/checkout_test.stamp'])

        check_files(['src/builds/01.py',
                     'versions/checkout_test.stamp',
                     'src/checkout1/Makefile.muddle',
                     'src/twolevel/checkout2/Makefile.muddle',
                     'src/multilevel/inner/checkout3/Makefile.muddle',
                     ])

def test_git_muddle_patch():
    """Test the workings of the muddle_patch program against git

    Relies upon test_git_checkout_build() having been called.
    """
    root_dir = normalise(os.getcwd())

    banner('Making changes in build1')
    with Directory('test_build1'):
        with Directory('src/checkout1'):
            touch('empty.c')      # empty
            touch('program1.c','// This is very dull C file 1\n')
            touch('program2.c','// This is very dull C file 2\n')
            touch('Makefile.muddle',
                  '# This is our makefile reduced to a single line\n')
            git('add empty.c program1.c program2.c Makefile.muddle')
            git('commit -m "Add program1|2.c, empty.c, shrink our Makefile"')
            muddle(['push'])  # muddle remembers the repository for us
            git('rm program2.c')
            touch('Makefile.muddle',
                  '# This is our makefile\n# Now with two lines\n')
            git('add Makefile.muddle')
            git('commit -m "Delete program2.c, change our Makefile"')
            muddle(['push'])  # muddle remembers the repository for us

        with Directory('src/twolevel/checkout2'):
            touch('program.c','// This is very dull C file\n')
            git('add program.c')
            git('commit -m "Add program.c"')
            muddle(['push'])  # muddle remembers the repository for us

        with Directory('src/multilevel/inner/checkout3'):
            touch('program.c','// This is very dull C file\n')
            git('add program.c')
            git('commit -m "Add program.c"')
            muddle(['push'])  # muddle remembers the repository for us

    banner('Generating patches between build1 (altered, near) and build3 (unaltered, far)')
    # test_build2 doesn't have a stamp file...
    with Directory('test_build1'):
        shell('%s write - ../test_build3/versions/checkout_test.stamp'
              ' ../patch_dir'%MUDDLE_PATCH_COMMAND)

    shell('ls patch_dir')

    banner('Applying patches to build3')
    with Directory('test_build3'):
        shell('%s read ../patch_dir'%MUDDLE_PATCH_COMMAND)

    with Directory('test_build1/src/checkout1'):
        git('rev-parse HEAD')
        git('rev-parse master')

    with Directory('test_build3/src/checkout1'):
        git('rev-parse HEAD')
        git('rev-parse master')
        banner('"git am" leaves our HEAD detached, so we should then do something like:')
        git('branch post-am-branch')    # to stop our HEAD being detached
        git('checkout master')          # assuming we were on master, of course
        git('merge post-am-branch')     # and we should now be where we want...
        git('rev-parse HEAD')
        git('rev-parse master')

    with Directory('test_build3/src/checkout1'):
        check_specific_files_in_this_dir(['Makefile.muddle', 'empty.c',
                                          'program1.c', '.git'])

    with Directory('test_build3/src/twolevel/checkout2'):
        check_specific_files_in_this_dir(['Makefile.muddle',
                                          'program.c', '.git'])

    with Directory('test_build3/src/multilevel/inner/checkout3'):
        check_specific_files_in_this_dir(['Makefile.muddle',
                                          'program.c', '.git'])

def test_bzr_muddle_patch():
    """Test the workings of the muddle_patch program against bzr

    Relies upon test_bzr_checkout_build() having been called.
    """
    root_dir = normalise(os.getcwd())

    banner('Making changes in build1')
    with Directory('test_build1'):
        with Directory('src/checkout1'):
            touch('empty.c')      # empty
            touch('program1.c','// This is very dull C file 1\n')
            touch('program2.c','// This is very dull C file 2\n')
            touch('Makefile.muddle',
                  '# This is our makefile reduced to a single line\n')
            bzr('add empty.c program1.c program2.c')
            bzr('commit -m "Add program1|2.c, empty.c, shrink our Makefile"')
            bzr('push')
            bzr('rm program2.c')
            touch('Makefile.muddle',
                  '# This is our makefile\n# Now with two lines\n')
            bzr('commit -m "Delete program2.c, change our Makefile"')
            bzr('push')

        with Directory('src/twolevel/checkout2'):
            touch('program.c','// This is very dull C file\n')
            bzr('add program.c')
            bzr('commit -m "Add program.c"')
            bzr('push')

        with Directory('src/multilevel/inner/checkout3'):
            touch('program.c','// This is very dull C file\n')
            bzr('add program.c')
            bzr('commit -m "Add program.c"')
            bzr('push')

    banner('TEMPORARY: MAKE VERSION STAMP FOR BUILD 1')
    with Directory('test_build1'):
        muddle(['stamp', 'version'])

    banner('Generating patches between build1 (altered, near) and build3 (unaltered, far)')
    # test_build2 doesn't have a stamp file...
    with Directory('test_build1'):
        shell('%s write - ../test_build3/versions/checkout_test.stamp'
              ' ../patch_dir'%MUDDLE_PATCH_COMMAND)

    shell('ls patch_dir')

    banner('Applying patches to build3')
    with Directory('test_build3'):
        shell('%s read ../patch_dir'%MUDDLE_PATCH_COMMAND)

    with Directory('test_build3/src/checkout1'):
        banner('Checking we have the expected files present...')
        check_specific_files_in_this_dir(['Makefile.muddle', 'program1.c', '.bzr'])
        # We'd *like* empty.c to be there as well, but at the moment
        # it won't be...

        banner('Committing the changes in checkout1')
        bzr('add')
        bzr('commit -m "Changes from muddle_patch"')

    with Directory('test_build3/src/twolevel/checkout2'):
        check_specific_files_in_this_dir(['Makefile.muddle',
                                          'program.c', '.bzr'])
        banner('Committing the changes in checkout2')
        bzr('add')
        bzr('commit -m "Changes from muddle_patch"')

    with Directory('test_build3/src/multilevel/inner/checkout3'):
        check_specific_files_in_this_dir(['Makefile.muddle',
                                          'program.c', '.bzr'])
        banner('Committing the changes in checkout3')
        bzr('add')
        bzr('commit -m "Changes from muddle_patch"')

def main(args):

    if not args or len(args) > 1:
        print __doc__
        return

    vcs = args[0]

    # Choose a place to work, rather hackily
    #root_dir = os.path.join('/tmp','muddle_tests')
    root_dir = normalise(os.path.join(os.getcwd(), 'transient'))

    if vcs == 'git':
        with TransientDirectory(root_dir, keep_on_error=True):
            banner('TEST SIMPLE BUILD (GIT)')
            test_git_simple_build()

        with TransientDirectory(root_dir, keep_on_error=True):
            banner('TEST CHECKOUT BUILD (GIT)')
            setup_git_checkout_repositories()
            test_git_checkout_build()
            banner('TEST MUDDLE PATCH (GIT)')
            test_git_muddle_patch()

    elif vcs == 'svn':
        with TransientDirectory(root_dir, keep_on_error=True):
            banner('TEST SIMPLE BUILD (SUBVERSION)')
            test_svn_simple_build()

    elif vcs == 'bzr':
        with TransientDirectory(root_dir, keep_on_error=True):
            banner('TEST SIMPLE BUILD (BZR)')
            test_bzr_simple_build()

        with TransientDirectory(root_dir, keep_on_error=True):
            banner('TEST CHECKOUT BUILD (BZR)')
            setup_bzr_checkout_repositories()
            test_bzr_checkout_build()
            banner('TEST MUDDLE PATCH (BZR)')
            test_bzr_muddle_patch()

    else:
        print 'Unrecognised VCS %s'%vcs

if __name__ == '__main__':
    args = sys.argv[1:]
    if args and args[0] == 'muddle':
        # Pretend to be muddle the command line program
        muddle(args[1:])
    else:
        main(args)

# vim: set tabstop=8 softtabstop=4 shiftwidth=4 expandtab: