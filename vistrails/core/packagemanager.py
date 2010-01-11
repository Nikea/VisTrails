###########################################################################
##
## Copyright (C) 2006-2010 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################

"""The package manager takes care of everything that has got to do
with handling packages, from setting paths to adding new packages
to checking dependencies to initializing them."""

import copy
import os
import sys
from PyQt4 import QtCore

from core import debug
from core.configuration import ConfigurationObject
import core.data_structures.graph
import core.db.io
from core.modules.module_registry import ModuleRegistry
from core.modules.package import Package
from core.utils import VistrailsInternalError, InstanceObject
##############################################################################


global _package_manager
_package_manager = None

class PackageManager(QtCore.QObject):
    # add_package_menu_signal is emitted with a tuple containing the package
    # identifier, package name and the menu item
    add_package_menu_signal = QtCore.SIGNAL("add_package_menu")
    # remove_package_menu_signal is emitted with the package identifier
    remove_package_menu_signal = QtCore.SIGNAL("remove_package_menu")
    #package_error_message_signal is emitted with the package identifier,
    # package name and the error message
    package_error_message_signal = QtCore.SIGNAL("package_error_message_signal")

    class DependencyCycle(Exception):
        def __init__(self, p1, p2):
            self._package_1 = p1
            self._package_2 = p2
        def __str__(self):
            return ("Packages '%s' and '%s' have cyclic dependencies" %
                    (self._package_1,
                     self._package_2))

    class MissingPackage(Exception):
        def __init__(self, n):
            self._package_name = n
        def __str__(self):
            return "Package '%s' is missing." % self._package_name

    class PackageInternalError(Exception):
        def __init__(self, n, d):
            self._package_name = n
            self._description = d
        def __str__(self):
            return "Package '%s' has a bug: %s" % (self._package_name,
                                                   self._description)

    def import_packages_module(self):
        """Imports the packages module using path trickery to find it
        in the right place.

        """
        if self._packages is not None:
            return self._packages
        # Imports standard packages directory
        conf = self._configuration
        old_sys_path = copy.copy(sys.path)
        if conf.check('packageDirectory'):
            sys.path.insert(0, conf.packageDirectory)
        try:
            import packages
        except ImportError:
            print 'ImportError: sys.path:', sys.path
            raise
        finally:
            sys.path = old_sys_path
        self._packages = packages
        return packages

    def import_user_packages_module(self):
        """Imports the packages module using path trickery to find it
        in the right place.

        """
        if self._userpackages is not None:
            return self._userpackages
        # Imports user packages directory
        conf = self._configuration
        old_sys_path = copy.copy(sys.path)
        if conf.check('userPackageDirectory'):
            sys.path.insert(0, os.path.join(conf.userPackageDirectory,
                                            os.path.pardir))
        try:
            import userpackages
        except ImportError:
            print 'ImportError: sys.path:', sys.path
            raise
        finally:
            sys.path = old_sys_path
        self._userpackages = userpackages
        return userpackages

    def __init__(self, configuration):
        """__init__(configuration: ConfigurationObject) -> PackageManager
        configuration is the persistent configuration object of the application.
        
        """
        global _package_manager
        if _package_manager:
            m = "Package manager can only be constructed once."
            raise VistrailsInternalError(m)
        QtCore.QObject.__init__(self)
        _package_manager = self
        self._configuration = configuration
        self._package_list = {}
        self._identifier_map = {}
        self._dependency_graph = core.data_structures.graph.Graph()
        self._registry = None
        self._userpackages = None
        self._packages = None

    def init_registry(self, registry_filename=None):
        if registry_filename is not None:
            self._registry = core.db.io.open_registry(registry_filename)
            self._registry.set_global()
        else:
            self._registry = ModuleRegistry()
            self._registry.set_global()

            def setup_basic_package():
                import core.modules.basic_modules

                # setup basic package
                basic_package = self.add_package('basic_modules')
                self._registry._default_package = basic_package
                package_dictionary = {'basic_modules': \
                                          core.modules.basic_modules}
                self.initialize_packages(package_dictionary)
            setup_basic_package()

    def finalize_packages(self):
        """Finalizes all installed packages. Call this only prior to
exiting VisTrails."""
        for package in self._package_list.itervalues():
            package.finalize()
        self._package_list = {}
        self._identifier_map = {}        
        global _package_manager
        _package_manager = None

    def add_package(self, packageName):
        """Adds a new package to the manager. This does not initialize it.
To do so, call initialize_packages()"""
        package = self._registry.create_package(packageName)
        self._package_list[packageName] = package
        return package

    def remove_package(self, codepath):
        """remove_package(name): Removes a package from the system."""
        pkg = self._package_list[codepath]
        self._dependency_graph.delete_vertex(pkg.identifier)
        del self._identifier_map[pkg.identifier]
        pkg.finalize()
        self.remove_menu_items(pkg)
        del self._package_list[codepath]
        self._registry.remove_package(pkg)

    def has_package(self, identifier):
        """has_package(identifer: string) -> Boolean.
Returns true if given package identifier is present."""
        return self._identifier_map.has_key(identifier)

    def look_at_available_package(self, codepath):
        """look_at_available_package(codepath: string) -> Package

        Returns a Package object for an uninstalled package. This does
        NOT install a package.
        """
        return self._registry.create_package(codepath, False)

    def get_package_by_codepath(self, codepath):
        """get_package_by_codepath(codepath: string) -> Package.
        Returns a package with given codepath if it is enabled,
        otherwise throws exception
        """
        if codepath not in self._package_list:
            raise self.MissingPackage(codepath)
        else:
            return self._package_list[codepath]

    def get_package_by_identifier(self, identifier):
        """get_package_by_identifier(identifier: string) -> Package.
        Returns a package with given identifier if it is enabled,
        otherwise throws exception
        """
        if identifier not in self._registry.packages:
            raise self.MissingPackage(identifier)
        return self._registry.packages[identifier]

#         # FIXME: This should really be handled better
#         if identifier == 'edu.utah.sci.vistrails.basic':
#             return InstanceObject(name='Basic Modules')
#         if identifier not in self._identifier_map:
#             raise self.MissingPackage(identifier)
#         else:
#             return self._identifier_map[identifier]

    def get_package_configuration(self, codepath):
        """get_package_configuration(codepath: string) ->
        ConfigurationObject or None

        Returns the configuration object for the package, if existing,
        or None. Throws MissingPackage if package doesn't exist.
        """

        pkg = self.get_package_by_codepath(codepath)

        if not hasattr(pkg.module, 'configuration'):
            return None
        else:
            c = pkg.module.configuration
            if not isinstance(c, ConfigurationObject):
                d = "'configuration' attribute should be a ConfigurationObject"
                raise self.PackageInternalError(codepath, d)
            return c

    def add_dependencies(self, package):
        """add_dependencies(package) -> None.  Register all
        dependencies a package contains by calling the appropriate
        callback.

        Does not add multiple dependencies - if a dependency is already there,
        add_dependencies ignores it.
        """
        deps = package.dependencies()
        # FIXME don't hardcode this
        from core.modules.basic_modules import identifier as basic_pkg
        if package.identifier != basic_pkg:
            deps.append(basic_pkg)
        missing_packages = [identifier
                            for identifier in deps
                            if identifier not in self._dependency_graph.vertices]
        if len(missing_packages):
            raise Package.MissingDependency(package,
                                            missing_packages)

        for dep_name in deps:
            if (dep_name not in
                self._dependency_graph.adjacency_list[package.identifier]):
                self._dependency_graph.add_edge(package.identifier, dep_name)

    def late_enable_package(self, package_codepath, package_dictionary={}):
        """late_enable_package enables a package 'late', that is,
        after VisTrails initialization. All dependencies need to be
        already enabled.
        """
        if package_codepath in self._package_list:
            raise VistrailsInternalError('duplicate package identifier: %s' %
                                         package_codepath)
        self.add_package(package_codepath)
        pkg = self.get_package_by_codepath(package_codepath)
        try:
            pkg.load(package_dictionary.get(pkg.codepath, None))
        except Exception, e:
            # invert self.add_package
            del self._package_list[package_codepath]
            raise
        self._dependency_graph.add_vertex(pkg.identifier)
        self._identifier_map[pkg.identifier] = pkg
        try:
            self.add_dependencies(pkg)
        except Exception, e:
            del self._identifier_map[pkg.identifier]
            self._dependency_graph.delete_vertex(pkg.identifier)
            # invert self.add_package
            del self._package_list[package_codepath]
            raise
        pkg.check_requirements()
        self._registry.initialize_package(pkg)
        self.add_menu_items(pkg)

    def late_disable_package(self, package_codepath):
        """late_disable_package disables a package 'late', that is,
        after VisTrails initialization. All reverse dependencies need to be
        already disabled.
        """
        pkg = self.get_package_by_codepath(package_codepath)
        self.remove_package(package_codepath)
        pkg.remove_own_dom_element()

    def initialize_packages(self,package_dictionary={}):
        """initialize_packages(package_dictionary={}): None

        Initializes all installed packages. If module_dictionary is
not {}, then it should be a dictionary from package names to preloaded
package-like objects (in theory they have to be modules that respect
the correct interface, but nothing actually prevents anyone from
creating a class that behaves similarly)."""
        packages = self.import_packages_module()
        userpackages = self.import_user_packages_module()

        failed = []
        # import the modules
        for package in self._package_list.itervalues():
            if package.initialized():
                continue
            try:
                package.load(package_dictionary.get(package.codepath, None))
            except Package.LoadFailed, e:
                debug.critical("Will disable package %s" % package.name)
                debug.critical(str(e))
                # print "FAILED TO LOAD, let's disable it"
                # We disable the package manually to skip over things
                # we know will not be necessary - the only thing needed is
                # the reference in the package list
                package.remove_own_dom_element()
                failed.append(package)
            except Package.InitializationFailed, e:
                debug.critical("Will disable package <codepath %s>" % package.codepath)
                debug.critical(str(e))
                # print "FAILED TO LOAD, let's disable it"
                # We disable the package manually to skip over things
                # we know will not be necessary - the only thing needed is
                # the reference in the package list
                package.remove_own_dom_element()
                failed.append(package)
            else:
                if self._dependency_graph.vertices.has_key(package.identifier):
                    raise VistrailsInternalError('duplicate package identifier: %s' %
                                                 package.identifier)
                self._dependency_graph.add_vertex(package.identifier)
                self._identifier_map[package.identifier] = package

        for pkg in failed:
            del self._package_list[pkg.codepath]
        failed = []

        # determine dependencies
        for package in self._package_list.itervalues():
            try:
                self.add_dependencies(package)
            except Package.MissingDependency, e:
                debug.critical("Will disable package %s" % package.name)
                debug.critical(str(e))
                # print "DEPENDENCIES FAILED TO LOAD, let's disable this"
                package.remove_own_dom_element()
                self._dependency_graph.delete_vertex(package.identifier)
                del self._identifier_map[package.identifier]
                failed.append(package)

        for pkg in failed:
            del self._package_list[pkg.codepath]

        # perform actual initialization
        try:
            g = self._dependency_graph.inverse_immutable()
            sorted_packages = g.vertices_topological_sort()
        except core.data_structures.graph.Graph.GraphContainsCycles, e:
            raise self.DependencyCycle(e.back_edge[0],
                                       e.back_edge[1])

        for name in sorted_packages:
            pkg = self._identifier_map[name]
            if not pkg.initialized():
                pkg.check_requirements()
                try:
                    self._registry.initialize_package(pkg)
                except Package.InitializationFailed, e:
                    debug.critical("Package initialization failed <codepath %s>" % pkg.codepath)
                    debug.critical("Will disable package <codepath %s>" % pkg.codepath)
                    debug.critical(str(e))
                    # print "FAILED TO LOAD, let's disable it"
                    # We disable the package manually to skip over things
                    # we know will not be necessary - the only thing needed is
                    # the reference in the package list
                    self.late_disable_package(pkg.codepath)
#                     pkg.remove_own_dom_element()
#                     failed.append(package)
                else:
                    self.add_menu_items(pkg)

    def add_menu_items(self, pkg):
        """add_menu_items(pkg: Package) -> None
        If the package implemented the function menu_items(),
        the package manager will emit a signal with the menu items to
        be added to the builder window """
        items = pkg.menu_items()
        if items:
            self.emit(self.add_package_menu_signal,
                      pkg.identifier,
                      pkg.name,
                      items)

    def remove_menu_items(self, pkg):
        """remove_menu_items(pkg: Package) -> None
        Send a signal with the pkg identifier. The builder window should
        catch this signal and remove the package menu items"""
        if pkg.menu_items():
            self.emit(self.remove_package_menu_signal,
                      pkg.identifier)

    def show_error_message(self, pkg, msg):
        """show_error_message(pkg: Package, msg: str) -> None
        Print a message to standard error output and emit a signal to the
        builder so if it is possible, a message box is also shown """
        print "Package %s (%s) says: %s"%(pkg.name,
                                         pkg.identifier,
                                         msg)
        self.emit(self.package_error_message_signal,
                  pkg.identifier,
                  pkg.name,
                  msg)

    def enabled_package_list(self):
        """package_list() -> returns list of all enabled packages."""
        return self._package_list.values()

    def identifier_is_available(self, identifier):
        """identifier_is_available(identifier: str) -> Pkg

        returns true if there exists a package with the given
        identifier in the list of available (ie, disabled) packages.

        If true, returns succesfully loaded, uninitialized package."""
        for codepath in self.available_package_names_list():
            try:
                pkg = self.get_package_by_codepath(codepath)
            except self.MissingPackage:
                pkg = self.look_at_available_package(codepath)
                try:
                    pkg.load()
                except pkg.LoadFailed:
                    pass
                except pkg.InitializationFailed:
                    pass
                if pkg.identifier == identifier:
                    return pkg
        return None

    def available_package_names_list(self):
        """available_package_names_list() -> returns list with code-paths of all
        available packages, by looking at the appropriate directories.

        The distinction between package names, identifiers and
        code-paths is described in doc/package_system.txt
        """

        lst = []

        def is_vistrails_package(path):
            return ((path.endswith('.py') and
                     not path.endswith('__init__.py') and
                     os.path.isfile(path)) or
                    os.path.isdir(path) and \
                        os.path.isfile(os.path.join(path, '__init__.py')))

        def visit(_, dirname, names):
            for name in names:
                if is_vistrails_package(os.path.join(dirname, name)):
                    if name.endswith('.py'):
                        name = name[:-3]
                    lst.append(name)
            # We want a shallow walk, so we prune the names list
            del names[:]

        # Finds standard packages
        packages = self.import_packages_module()
        os.path.walk(os.path.dirname(packages.__file__), visit, None)
        userpackages = self.import_user_packages_module()
        os.path.walk(os.path.dirname(userpackages.__file__), visit, None)

        return lst

    def dependency_graph(self):
        """dependency_graph() -> Graph.  Returns a graph with package
        dependencies, where u -> v if u depends on v.  Vertices are
        strings representing package names."""
        return self._dependency_graph

    def can_be_disabled(self, identifier):
        """Returns whether has no reverse dependencies (other
        packages that depend on it."""
        return self._dependency_graph.in_degree(identifier) == 0

    def reverse_dependencies(self, identifier):
        lst = [x[0] for x in
               self._dependency_graph.inverse_adjacency_list[identifier]]
        return lst

def get_package_manager():
    global _package_manager
    if not _package_manager:
        raise VistrailsInternalError("package manager not constructed yet.")
    return _package_manager

##############################################################################
