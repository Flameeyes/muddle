"""
Collect deployment.

Principally depending on other deployments, this 
deployment is used to collect elements built by
other parts of the system into a directory -
usually to be processed by some external tool.
"""

import muddled.pkg as pkg
import muddled.depend as depend
import muddled.utils as utils
import muddled.deployment as deployment
import os

class AssemblyDescriptor:
    def __init__(self, from_label, from_rel, to_name, recursive = True, 
                 failOnAbsentSource = False, 
                 copyExactly = True,
                 usingRSync = False):
        """
        Construct an assembly descriptor.

        We copy from the directory from_rel in from_label 
        (package, deployment, checkout) to the name to_name under
        the deployment.

        Give a package of '*' to copy from the install directory
        for a given role.

        If recursive is True, we'll copy recursively.

        * failOnAbsentSource - If True, we'll fail if the source doesn't exist.
        * copyExactly        - If True, keeps links. If false, copies the file
          they point to.
        """
        self.from_label = from_label
        self.from_rel = from_rel
        self.to_name = to_name
        self.recursive = recursive
        self.using_rsync = usingRSync
        self.fail_on_absent_source = failOnAbsentSource
        self.copy_exactly = copyExactly

        
    def get_source_dir(self, builder):
        if (self.from_label.type == utils.LabelType.Checkout):
            return builder.invocation.checkout_path(self.from_label)
        elif (self.from_label.type == utils.LabelType.Package):
            if ((self.from_label.name is None) or 
                self.from_label.name == "*"):
                return builder.invocation.role_install_path(self.from_label.role,
                                                            domain=self.from_label.domain)
            else:
                return builder.invocation.package_obj_path(self.from_label)
        elif (self.from_label.type == utils.LabelType.Deployment):
            return builder.invocation.deploy_path(self.from_label.name,
                                                  domain=self.from_label.domain)
        else:
            raise utils.GiveUp("Label %s for collection action has unknown kind."%(self.from_label))

class CollectDeploymentBuilder(pkg.Action):
    """
    Builds the specified collect deployment.
    """

    def __init__(self):
        self.assemblies = [ ]

    def add_assembly(self, assembly_descriptor):
        self.assemblies.append(assembly_descriptor)

    def _inner_labels(self):
        """
        Return any "inner" labels, so their domains may be altered.
        """
        labels = []
        for assembly in self.assemblies:
            labels.append(assembly.from_label)
        return labels

    def build_label(self, builder, label):
        """
        Actually do the copies ..
        """

        utils.ensure_dir(builder.invocation.deploy_path(label.name, domain=label.domain))

        if (label.tag == utils.LabelTag.Deployed):
            for asm in self.assemblies:
                src = os.path.join(asm.get_source_dir(builder), asm.from_rel)
                dst = os.path.join(builder.invocation.deploy_path(label.name, domain=label.domain), 
                                   asm.to_name)

                if (not os.path.exists(src)):
                    if (asm.fail_on_absent_source):
                        raise utils.GiveUp("Deployment %s: source object %s does not exist."%(label.name, src))
                    # Else no one cares :-)
                else:
                    if (asm.using_rsync):
                        # Use rsync for speed
                        try:
                            os.makedirs(dst)
                        except OSError:
                            pass

                        xdst = dst
                        if xdst[-1] != "/":
                            xdst = xdst + "/"

                        utils.run_cmd("rsync -avz \"%s/.\" \"%s\""%(src,xdst))
                    elif (asm.recursive):
                        utils.recursively_copy(src, dst, object_exactly = asm.copy_exactly)
                    else:
                        utils.copy_file(src, dst, object_exactly = asm.copy_exactly)
        else:
            pass


def deploy(builder, name):
    """
    Create a collection deployment builder.

    This adds a new rule linking the label ``deployment:<name>/deployed``
    to the collection deployment builder.

    You can then add assembly descriptors using the other utility functions in
    this module.

    Dependencies get registered when you add an assembly descriptor.
    """
    the_action = CollectDeploymentBuilder()

    dep_label = depend.Label(utils.LabelType.Deployment,
                             name, None,
                             utils.LabelTag.Deployed)

    deployment_rule = depend.Rule(dep_label, the_action)

    # We need to clean it as well, annoyingly .. 
    deployment.register_cleanup(builder, name)

    builder.invocation.ruleset.add(deployment_rule)

def copy_from_checkout(builder, name, checkout, rel, dest, 
                       recursive = True, 
                       failOnAbsentSource = False, 
                       copyExactly = True,
                       domain = None,
                       usingRSync = False):
    rule = deployment.deployment_rule_from_name(builder, name)
    
    dep_label = depend.Label(utils.LabelType.Checkout,
                             checkout, 
                             None,
                             utils.LabelTag.CheckedOut,
                             domain=domain)

    asm = AssemblyDescriptor(dep_label, rel, dest, recursive = recursive,
                             failOnAbsentSource = failOnAbsentSource, 
                             copyExactly = copyExactly,
                             usingRSync = usingRSync)
    rule.add(dep_label)
    rule.obj.add_assembly(asm)

def copy_from_package_obj(builder, name, pkg_name, pkg_role, rel,dest,
                          recursive = True,
                          failOnAbsentSource = False,
                          copyExactly = True,
                          domain = None,
                          usingRSync = False):
    """
      - If 'usingRSync' is true, copy with rsync - substantially faster than
           cp, if you have rsync. Not very functional if you don't :-)
    """

    rule = deployment.deployment_rule_from_name(builder, name)
    
    dep_label = depend.Label(utils.LabelType.Package,
                             pkg_name, pkg_role,
                             utils.LabelTag.Built,
                             domain=domain)
    asm = AssemblyDescriptor(dep_label, rel, dest, recursive = recursive,
                             failOnAbsentSource = failOnAbsentSource, 
                             copyExactly = copyExactly,
                             usingRSync = usingRSync)
    rule.add(dep_label)
    rule.obj.add_assembly(asm)

def copy_from_role_install(builder, name, role, rel, dest,
                           recursive = True,
                           failOnAbsentSource = False,
                           copyExactly = True,
                           domain = None,
                           usingRSync = False):
    """
    Add a requirement to copy from the given role's install to the named deployment.

    'name' is the name of the collecting deployment, as created by::

        deploy(builder, name)

    which is remembered as a rule whose target is ``deployment:<name>/deployed``,
    where <name> is the 'name' given.

    'role' is the role to copy from. Copying will be based from 'rel' within
    the role's ``install``, to 'dest' within the deployment.

    The label ``package:(<domain>)*{<role>}/postinstalled`` will be added as a
    dependency of the collecting deployment rule.

    An AssemblyDescriptor will be created to copy from 'rel' in the install
    directory of the label ``package:*{<role>}/postinstalled``, to 'dest'
    within the deployment directory of 'name', and added to the rule's actions.

    So, for instance::

        copy_from_role_install(builder,'fred','data','public','data/public',
                               True, False, True)

    might copy (recursively) from::

        install/data/public

    to::

        deploy/fred/data/public

    'rel' may be the empty string ('') to copy all files in the install
    directory.

    - If 'recursive' is true, then copying is recursive, otherwise it is not.
    - If 'failOnAbsentSource' is true, then copying will fail if the source
      does not exist.
    - If 'copyExactly' is true, then symbolic links will be copied as such,
      otherwise the linked file will be copied.
    - If 'usingRSync' is true, copy with rsync - substantially faster than
         cp, if you have rsync. Not very functional if you don't :-)
    """
    rule = deployment.deployment_rule_from_name(builder, name)
    dep_label = depend.Label(utils.LabelType.Package,
                             "*",
                             role,
                             utils.LabelTag.PostInstalled,
                             domain=domain)
    asm = AssemblyDescriptor(dep_label, rel, dest, recursive = recursive,
                             failOnAbsentSource = failOnAbsentSource, 
                             copyExactly = copyExactly,
                             usingRSync = usingRSync)
    rule.add(dep_label)
    rule.obj.add_assembly(asm)

def copy_from_deployment(builder, name, dep_name, rel, dest,
                         recursive = True,
                         failOnAbsentSource = False,
                         copyExactly = True,
                         domain = None,
                         usingRSync = False):
    """
    usingRSync - set to True to copy with rsync - substantially faster than
                 cp
    """
    rule = deployment.deployment_rule_from_name(builder,name)
    dep_label = depend.Label(utils.LabelType.Deployment,
                             dep_name, 
                             None, 
                             utils.LabelTag.Deployed,
                             domain=domain)
    asm = AssemblyDescriptor(dep_label, rel, dest, recursive = recursive,
                             failOnAbsentSource = failOnAbsentSource, 
                             copyExactly = copyExactly,
                             usingRSync = usingRSync)
    rule.add(dep_label)
    rule.obj.add_assembly(asm)


# End file.
