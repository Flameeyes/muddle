"""
Multi-level checkouts. Required for embedding things like android, which
have a lot of deep internal checkouts.
"""

import muddled
import muddled.pkg as pkg
import muddled.version_control as version_control
import muddled.utils as utils
from muddled.depend import Label

import urlparse
import os


def relative(builder, co_dir, co_name, repo_relative = None, rev = None,
             branch = None):
    """
    A multilevel version of checkout.simple.relative()

    See the docs for twolevel.relative() for details; multilevel checkouts
    are distinguished by having a different checkout name from their
    directory entirely, which is a bit confusing, but also allows for
    multiple repositories all called the same thing - again, this is an
    adaptation for things like android which actually require it.

    NB: Although the argument 'repo_relative' is provided, it is ignored.
    For the moment, multilevel checkouts must be in the same location on
    the repository as given in the 'co_dir' argument.
    """
    repo = builder.invocation.db.repo.get()

    co_label = Label(utils.LabelType.Checkout, co_name, domain=builder.default_domain)
    builder.invocation.db.set_checkout_path(co_label, co_dir)

    # Version control is slightly weird here ..
    (d, n) = os.path.split(co_dir)

    # We have to lie a bit here and reconstruct repo as the classic
    #  two-level resolver doesn't really work.
    real_repo = os.path.join(repo, co_dir)

    #print 'VCS',co_name
    #print '... full co_dir',co_dir
    #print '... co_dir',d
    #print '... co_in',n

    vcs_handler = version_control.vcs_dependable_for(builder,
                                                     co_label,
                                                     real_repo, rev,
                                                     None,
                                                     co_dir = d,
                                                     co_in = n,
                                                     branch = branch)
    pkg.add_checkout_rules(builder.invocation.ruleset,
                           co_name,
                           vcs_handler)

# def absolute(builder, co_dir, co_name, repo_url, rev = None):

# End file.