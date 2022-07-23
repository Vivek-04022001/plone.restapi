from AccessControl import getSecurityManager
from itertools import chain
from plone.app.workflow.browser.sharing import merge_search_results
from plone.restapi.interfaces import ISerializeToJson, ISerializeToJsonSummary
from plone.restapi.services import Service
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import normalizeString
from urllib.parse import parse_qs
from zExceptions import BadRequest
from zope.component import getMultiAdapter
from zope.component import queryMultiAdapter
from zope.component.hooks import getSite
from zope.interface import implementer
from zope.publisher.interfaces import IPublishTraverse


DEFAULT_SEARCH_RESULTS_LIMIT = 25


@implementer(IPublishTraverse)
class UsersGet(Service):
    def __init__(self, context, request):
        super().__init__(context, request)
        self.params = []
        portal = getSite()
        self.portal_membership = getToolByName(portal, "portal_membership")
        self.acl_users = getToolByName(portal, "acl_users")
        self.query = parse_qs(self.request["QUERY_STRING"])
        self.search_term = self.query.get("search", [""])[0]

    def publishTraverse(self, request, name):
        # Consume any path segments after /@users as parameters
        self.params.append(name)
        return self

    @property
    def _get_user_id(self):
        if len(self.params) != 1:
            raise Exception("Must supply exactly one parameter (user id)")
        return self.params[0]

    def _get_user(self, user_id):
        return self.portal_membership.getMemberById(user_id)

    @staticmethod
    def _sort_users(users):
        users.sort(
            key=lambda x: x is not None
            and normalizeString(x.getProperty("fullname", ""))
        )
        return users

    def _principal_search_results(
        self, search_for_principal, get_principal_by_id, principal_type, id_key
    ):

        hunter = getMultiAdapter((self.context, self.request), name="pas_search")

        principals = []
        for principal_info in search_for_principal(hunter, self.search_term):
            principal_id = principal_info[id_key]
            principals.append(get_principal_by_id(principal_id))

        return principals

    def _get_users(self):
        results = {user["userid"] for user in self.acl_users.searchUsers()}
        users = [self.portal_membership.getMemberById(userid) for userid in results]
        return self._sort_users(users)

    def _user_search_results(self):
        def search_for_principal(hunter, search_term):
            return merge_search_results(
                chain(
                    *(
                        hunter.searchUsers(**{field: search_term})
                        for field in ["name", "fullname", "email"]
                    )
                ),
                "userid",
            )

        def get_principal_by_id(user_id):
            mtool = getToolByName(self.context, "portal_membership")
            return mtool.getMemberById(user_id)

        return self._principal_search_results(
            search_for_principal, get_principal_by_id, "user", "userid"
        )

    def _get_filtered_users(self, query, groups_filter, search_term, limit):
        """Filter or search users by id, fullname, email and/or groups.

        Args:
            query (str): filter by query
            groups_filter (list of str): list of groups
            search_term (str): search by id, fullname, email
            limit (integer): limit result

        Returns:
            list: list of users sorted by fullname
        """
        if search_term:
            users = self._user_search_results()
        else:
            results = self.acl_users.searchUsers(id=query, max_results=limit)
            users = [
                self.portal_membership.getMemberById(user["userid"]) for user in results
            ]
        if groups_filter:
            users = [
                user for user in users if set(user.getGroups()) & set(groups_filter)
            ]
        return self._sort_users(users)

    def has_permission_to_query(self):
        sm = getSecurityManager()
        return sm.checkPermission("Manage portal", self.context)

    def has_permission_to_enumerate(self):
        sm = getSecurityManager()
        return sm.checkPermission("Manage portal", self.context)

    def has_permission_to_access_user_info(self):
        sm = getSecurityManager()
        return sm.checkPermission(
            "plone.restapi: Access Plone user information", self.context
        )

    def reply(self):
        if len(self.query) > 0 and len(self.params) == 0:
            query = self.query.get("query", "")
            groups_filter = self.query.get("groups-filter:list", [])
            limit = self.query.get("limit", [DEFAULT_SEARCH_RESULTS_LIMIT])[0]
            if query or groups_filter or self.search_term or limit:
                if self.has_permission_to_query():
                    users = self._get_filtered_users(
                        query, groups_filter, self.search_term, limit
                    )
                    result = []
                    for user in users:
                        serializer = queryMultiAdapter(
                            (user, self.request), ISerializeToJson
                        )
                        result.append(serializer())
                    return result
                else:
                    self.request.response.setStatus(401)
                    return
            else:
                raise BadRequest("Parameters supplied are not valid")

        if len(self.params) == 0:
            # Someone is asking for all users, check if they are authorized
            if self.has_permission_to_enumerate():
                result = []
                for user in self._get_users():
                    serializer = queryMultiAdapter(
                        (user, self.request), ISerializeToJson
                    )
                    result.append(serializer())
                return result
            else:
                self.request.response.setStatus(401)
                return

        # Some is asking one user, check if the logged in user is asking
        # their own information or if they are a Manager
        current_user_id = self.portal_membership.getAuthenticatedMember().getId()

        if self.has_permission_to_access_user_info() or (
            current_user_id and current_user_id == self._get_user_id
        ):

            # we retrieve the user on the user id not the username
            user = self._get_user(self._get_user_id)
            if not user:
                self.request.response.setStatus(404)
                return
            serializer = queryMultiAdapter(
                (user, self.request), ISerializeToJsonSummary
            )
            return serializer()
        else:
            self.request.response.setStatus(401)
            return
