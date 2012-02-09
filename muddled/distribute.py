"""
Actions and mechanisms relating to distributing build trees
"""

import os

from muddled.depend import Action, Rule
from muddled.utils import GiveUp, MuddleBug, LabelTag, LabelType, \
        copy_without, normalise_dir
from muddled.version_control import get_vcs_handler

def distribute_checkout(builder, name, label, copy_vcs_dir=False):
    """Request the distribution of the given checkout.

    - 'name' is the name of this distribution
    - 'label' must be a checkout label, but the tag is not important.

    By default, we don't copy any VCS directory.

    Notes:

        1. If we already described a distribution called 'name' for 'label',
           then this will silently overwrite it.
    """
    if label.type != LabelType.Checkout:
        raise MuddleBug('Attempt to use non-checkout label %s for a distribute checkout rule'%label)

    source_label = label.copy_with_tag(LabelTag.CheckedOut)
    target_label = label.copy_with_tag(LabelTag.Distributed)

    # Is there already a rule for distributing this label?
    if builder.invocation.target_label_exists(target_label):
        # Yes - add this distribution to it (if it's not there already)
        action = builder.invocation.ruleset.map[target_label]
        action.add_distribution(name, copy_vcs_dir)
    else:
        # No - we need to create one
        action = DistributeCheckout(name, copy_vcs_dir)

        rule = Rule(target_label, action)       # to build target_label, run action
        rule.add(source_label)                  # after we've built source_label

        builder.invocation.ruleset.add(rule)

def distribute_build_description(builder, name, label, copy_vcs_dir=False):
    """Request the distribution of the build description checkout.

    - 'context' is a DistributeContext instance, naming the builder and the
      target directory
    - 'label' must be a checkout label, but the tag is not important.

    By default, don't copy any VCS directory.
    """
    # For the moment, just like any other checkout
    distribute_checkout(builder, name, label, copy_vcs_dir)

def distribute_package(builder, name, label, binary=True, source=False, copy_vcs_dir=False):
    """Request the distribution of the given package.

    - 'context' is a DistributeContext instance, naming the builder and the
      target directory
    - 'label' must be a package label, but the tag is not important.

    - If 'binary' is true, then a binary distribution will be performed.
      This means that obj/ and install/ directories (and the associated
      muddle tags) will be copied.

    - If 'source' is true, then a source distribution will be performed.
      This means that the source directories (within src/) for the checkouts
      directly used by the package will be copied, along with the
      associated muddle tags. If 'source' is true and 'copy_vcs_dir' is
      true, then the VCS directories for those source checkouts will also
      be copied, otherwise they will not.

    Notes:

        1. We don't forbid having both 'binary' and 'source' true,
           but this may change in the future.
        2. If the package directly uses more than one checkout, then
           'copy_vcs_dir' applies to all of them. It is not possible
           to give different values for different checkouts.
        3. You can determine which checkouts 'source' distribution will
           use with "muddle -n import <package_label>" (or "muddle -n"
           with the package label for any "checkout" command).
        4. If we already described a distribution called 'name' for 'label',
           then this will silently overwrite it.
    """
    if label.type != LabelType.Package:
        raise MuddleBug('Attempt to use non-package label %s for a distribute package rule'%label)

    source_label = label.copy_with_tag(LabelTag.PostInstalled)
    target_label = label.copy_with_tag(LabelTag.Distributed)

    # Is there already a rule for distributing this label?
    if builder.invocation.target_label_exists(target_label):
        # Yes - add this distribution name to it (if it's not there already)
        action = builder.invocation.ruleset.map[target_label]
        action.add_context_name(name)
    else:
        # No - we need to create one
        action = DistributePackage(name)

        rule = Rule(target_label, action)       # to build target_label, run action
        rule.add(source_label)                  # after we've built source_label

        builder.invocation.ruleset.add(rule)

def _actually_distribute_checkout(builder, label, target_dir, copy_vcs_dir):
    """As it says.
    """
    # 1. We know the target directory. Note it may not exist yet
    # 2. Get the actual directory of the checkout
    co_dir = builder.invocation.db.get_checkout_location(label)
    # 3. If we're not doing copy_vcs_dir, find the VCS for this
    #    checkout, and from that determine its VCS dir, and make
    #    that our "without" string
    without = []
    if not copy_vcs_dir:
        repo = builder.invocation.db.get_checkout_repo(label)
        vcs_handler = get_vcs_handler(repo.vcs)
        vcs_dir = vcs_handler.get_vcs_dirname()
        if vcs_dir:
            without.append(vcs_dir)
    # 4. Do a copywithout to do the actual copy, suitably ignoring
    #    the VCS directory if necessary.
    target_dir = os.path.join(normalise_dir(target_dir), co_dir)
    print 'Copying:'
    print '  from %s'%co_dir
    print '  to   %s'%target_dir
    if not copy_vcs_dir:
        print '  without %s'%vcs_dir
    copy_without(co_dir, target_dir, without, preserve=True)
    # 5. Set the appropriate tags in the target .muddle/ directory
    # 6. Set the /distributed tag on the checkout

def _actually_distribute_binary(builder, label, target_dir):
    """Do a binary distribution of our package.
    """
    # 1. We know the target directory. Note it may not exist yet
    # 2. Get the actual directory of the package obj/ and install/
    #    directories
    obj_dir = builder.invocation.package_obj_path(label)
    install_dir = builder.invocation.package_install_path(label)
    # 3. Use copywithout to copy the obj/ and install/ directories over
    root_path = normalise_dir(builder.invocation.db.root_path)
    rel_obj_dir = os.path.relpath(normalise_dir(obj_dir), root_path)
    rel_install_dir = os.path.relpath(normalise_dir(install_dir), root_path)

    target_obj_dir = os.path.join(target_dir, rel_obj_dir)
    target_install_dir = os.path.join(target_dir, rel_install_dir)

    target_obj_dir = normalise_dir(target_obj_dir)
    target_install_dir = normalise_dir(target_install_dir)

    print 'Copying:'
    print '  from %s'%obj_dir
    print '  and  %s'%install_dir
    print '  to   %s'%target_obj_dir
    print '  and  %s'%target_install_dir

    copy_without(obj_dir, target_obj_dir, preserve=True)
    copy_without(install_dir, target_install_dir, preserve=True)
    # 4. Set the appropriate tags in the target .muddle/ directory
    # 5. Set the /distributed tag on the package

class DistributeAction(Action):
    """
    An action that distributes a something-or-other.

    Intended as a base class for actions that know what they're doing.

    We contain one thing: a dictionary of {name : distribution information}.
    """

    def __init__(self, name, data):
        """
        'name' is the name of a distribution that this action supports.

        'data' is the data that describes how we do the distribution - this
        will differ according to whether we are distributing a checkout or
        package.
        """
        self.distributions = {name:data}

    def add_distribution(self, name, data):
        """Add another distribution to this action.
        """
        self.distributions[name] = data

    def get_distribution(self, name):
        """Return the data for distribution 'name', or raise MuddleBug
        """
        try:
            return self.distributions[name]
        except KeyError:
            raise MuddleBug('This Action does not have data for distribution "%s"'%name)

    def does_distribution(self, name):
        """Return True if we know this distribution name, False if not.
        """
        return name in self.distributions

    def build_label(self, builder, label):
        """Override this to do the actual task of distribution.
        """
        raise MuddleBug('No build_label method defined for class'
                        ' %s'%self.__class__.__name__)

class DistributeCheckout(DistributeAction):
    """
    An action that distributes a checkout.

    It copies the checkout source directory.

    By default it does not copy any VCS subdirectory (.git/, etc.)
    """

    def __init__(self, name, copy_vcs_dir=False):
        """
        'name' is the name of a DistributuionContext. When created, we are
        told which DistributionContext we can be distributed by. Later on,
        other names may be added...

        If 'copy_vcs_dir' is false, then don't copy any VCS directory
        (.git/, .bzr/, etc., depending on the VCS used for this checkout).
        """
        super(DistributeCheckout, self).__init__(name, copy_vcs_dir)

    def build_label(self, builder, label):
        name, target_dir = builder.get_distribution()

        copy_vcs_dir = self.distributions[name]

        print 'DistributeCheckout %s (%s VCS dir) to %s'%(label,
                'without' if copy_vcs_dir else 'with', target_dir)

        _actually_distribute_checkout(builder, label, target_dir, copy_vcs_dir)

class DistributeBuildDescription(DistributeCheckout):
    """
    An action that distributes a build description's checkout.

    It copies the checkout source directory.

    By default it does not copy any VCS subdirectory (.git/, etc.)

    For the moment, it is identical to DistributeCheckout, but that will
    not be so when it is finished
    """
    pass

class DistributePackage(DistributeAction):
    """
    An action that distributes a package.

    If the package is being distributed as binary, then this action copies
    the obj/ and install/ directories for the package, as well as any
    instructions (and anything else I haven't yet thought of).

    If the package is being distributed as source, then this action copies
    the source directory for each checkout that is *directly* used by the
    package.

    In either case, associated and appropriate muddle tags are also copied.

    Destination directories that do not exist are created as necessary.
    """

    def __init__(self, name, binary=True, source=False, copy_vcs_dir=False):
        """
        'name' is the name of a DistributuionContext. When created, we are
        told which DistributionContext we can be distributed by. Later on,
        other names may be added...

        If 'binary' is true, then a binary distribution will be performed.
        This means that obj/ and install/ directories (and the associated
        muddle tags) will be copied.

        If 'source' is true, then a source distribution will be performed.
        This means that the source directories (within src/) for the checkouts
        directly used by the package will be copied, along with the
        associated muddle tags. If 'source' is true and 'copy_vcs_dir' is
        true, then the VCS directories for those source checkouts will also
        be copied, otherwise they will not.

        Notes:

            1. We don't forbid having both 'binary' and 'source' true,
               but this may change in the future.
            2. If the package directly uses more than one checkout, then
               'copy_vcs_dir' applies to all of them. It is not possible
               to give different values for different checkouts.
            3. You can determine which checkouts 'source' distribution will
               use with "muddle -n import <package_label>" (or "muddle -n"
               with the package label for any "checkout" command).
        """
        super(DistributePackage, self).__init__(name, (binary, source, copy_vcs_dir))

    def build_label(self, builder, label):
        name, target_dir = builder.get_distribution()

        binary, source, copy_vcs_dir = self.distributions[name]

        print 'DistributePackage %s to %s'%(label, target_dir)

        if binary:
            _actually_distribute_binary(builder, label, target_dir)

        if source:
            checkouts = builder.invocation.checkouts_for_package(label)
            for co_label in checkouts:
                _actually_distribute_checkout(builder, co_label,
                                              target_dir, self.copy_vcs_dir)


def distribute(builder, target_dir, name, unset_tags=False):
    """Distribute using distribution context 'name', to 'target_dir'.

    The DistributeContext called 'name' must exist.

    All distributions described in that DistributeContext will be made.

    'target_dir' need not exist - it will be created if necessary.

    If 'unset_tags' is true, then we unset the /distribute tags for our
    labels before doing the distribution.
    """

    distribution_labels = set()

    invocation = builder.invocation
    target_label_exists = invocation.target_label_exists

    # We get all the "reasonable" checkout and package labels
    all_checkouts = builder.invocation.all_checkout_labels()
    all_packages = builder.invocation.all_package_labels()

    combined_labels = all_checkouts.union(all_packages)
    for label in combined_labels:
        target = label.copy_with_tag(LabelTag.Distributed)
        # Is there a distribution target for this label?
        if target_label_exists(target):
            # If so, is it distributable with this distribution name?
            rule = invocation.ruleset.map[target]
            if rule.action.does_distribution(name):
                # Yes, we like this label
                distribution_labels.add(target)

    distribution_labels = list(distribution_labels)
    distribution_labels.sort()

    if unset_tags:
        print 'Killing /distribute labels'
        for label in distribution_labels:
            builder.kill_label(label)

    # Remember to say where we're copying to...
    builder.set_distribution(name, target_dir)

    print 'Building /distribute labels'
    for label in distribution_labels:
        builder.build_label(label)

    # XXX TODO
    # Question - what are we meant to do if a package implicitly sets
    # a distribution state for a checkout, and we also explicitly set
    # a different (incompatible) state for a checkout? Who wins? Or do
    # we just try to satisfy both?
