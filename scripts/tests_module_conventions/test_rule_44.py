"""Control cases for the rule 44 module-convention rules."""

from __future__ import annotations

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)


def test_role_check_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_44_role_checks, module) == []

    billing_style = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def recheck(user, organization):\n"
            "    membership_model = apps.get_model(\n"
            '        "quickscale_orgs",\n'
            '        "OrganizationMembership",\n'
            "    )\n"
            "    return membership_model._default_manager.filter(\n"
            "        user=user,\n"
            "        organization=organization,\n"
            '        role="owner",\n'
            "    ).exists()\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, billing_style)
    )

    direct = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    return OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, direct)
    )

    aliased = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership as Membership\n\n\n"
            "def owners():\n"
            '    return Membership.objects.exclude(role="owner")\n'
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, aliased)
    )

    chained = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(user):\n"
            "    return (\n"
            "        OrganizationMembership.objects\n"
            "        .select_for_update()\n"
            "        .filter(user=user)\n"
            '        .filter(role="owner")\n'
            "    )\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, chained)
    )

    dotted_lookup = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user):\n"
            '    membership_model = apps.get_model("quickscale_orgs.OrganizationMembership")\n'
            "    return membership_model.objects.filter(user=user, role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, dotted_lookup)
    )

    lowercase_dotted = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user):\n"
            '    membership_model = apps.get_model("quickscale_orgs.organizationmembership")\n'
            "    return membership_model.objects.filter(user=user, role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, lowercase_dotted)
    )

    lowercase_two_argument = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user):\n"
            '    membership_model = apps.get_model("quickscale_orgs", "organizationmembership")\n'
            "    return membership_model.objects.filter(user=user, role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, lowercase_two_argument)
    )

    inline_lookup = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user, organization):\n"
            "    return (\n"
            '        apps.get_model("quickscale_orgs", "OrganizationMembership")\n'
            "        .objects.filter(user=user, organization=organization, role='owner')\n"
            "    )\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, inline_lookup)
    )

    queryset_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(user):\n"
            "    memberships = OrganizationMembership.objects.filter(user=user)\n"
            "    return memberships.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, queryset_binding)
    )

    async_query = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "async def owners(user, organization):\n"
            "    return await OrganizationMembership.objects.aget(\n"
            "        user=user, organization=organization, role='owner'\n"
            "    )\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, async_query)
    )

    async_role_member = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrgRole, OrganizationMembership\n\n\n"
            "async def owners(user, organization):\n"
            "    return await OrganizationMembership.objects.aget(\n"
            "        user=user, organization=organization, role=OrgRole.OWNER\n"
            "    )\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, async_role_member) == []

    unrelated_app = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user):\n"
            '    other_model = apps.get_model("another_app", "OrganizationMembership")\n'
            "    return other_model.objects.filter(user=user, role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, unrelated_app) == []

    unrelated_inline = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from django.apps import apps\n\n\n"
            "def owners(user):\n"
            "    return (\n"
            '        apps.get_model("another_app", "OrganizationMembership")\n'
            "        .objects.filter(user=user, role='owner')\n"
            "    )\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, unrelated_inline) == []

    sibling_scopes = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def memberships(user):\n"
            "    qs = OrganizationMembership.objects.filter(user=user)\n"
            "    return qs.filter(role='owner')\n\n\n"
            "def contacts(user):\n"
            "    qs = Contact.objects.filter(user=user)\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    found = _violations(checker.rule_44_role_checks, sibling_scopes)
    assert len(found) == 1, found
    assert "services.py:9" in found[0]

    shadowed_local = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts(user):\n"
            "    qs = Contact.objects.filter(user=user)\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, shadowed_local) == []

    shadowed_parameter = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts(qs):\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, shadowed_parameter) == []

    default_argument = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(qs=OrganizationMembership.objects.filter(role='owner')):\n"
            "    return qs\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, default_argument)
    )

    class_rebinding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "class Owners:\n"
            "    qs = qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, class_rebinding)
    )

    global_rebinding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def owners(user):\n"
            "    global qs\n"
            "    qs = qs.filter(user=user)\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, global_rebinding)
    )

    match_capture = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts(contact):\n"
            "    match contact:\n"
            "        case {'queryset': qs}:\n"
            "            return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, match_capture) == []

    comprehension_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts():\n"
            "    return [qs.filter(role='owner') for qs in Contact.objects.all()]\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, comprehension_shadow) == []

    lambda_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts():\n"
            "    return map(lambda qs: qs.filter(role='owner'), Contact.objects.all())\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, lambda_shadow) == []

    nested_global = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def outer():\n"
            "    qs = Contact.objects.all()\n\n"
            "    def owners():\n"
            "        global qs\n"
            "        return qs.filter(role='owner')\n\n"
            "    return owners\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, nested_global)
    )

    match_after = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts(contact):\n"
            "    match contact:\n"
            "        case {'queryset': qs}:\n"
            "            pass\n"
            "        case _:\n"
            "            return None\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, match_after) == []

    with_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    with transaction.atomic():\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, with_binding)
    )

    with_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts():\n"
            "    with transaction.atomic():\n"
            "        qs = Contact.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, with_shadow) == []

    branch_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(cond):\n"
            "    if cond:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, branch_binding)
    )

    try_else = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    try:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    except Exception:\n"
            "        return None\n"
            "    else:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, try_else)
    )

    class_method = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "class Owners:\n"
            "    qs = Contact.objects.all()\n\n"
            "    def owners(self):\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, class_method)
    )

    class_method_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = Contact.objects.all()\n\n\n"
            "class Owners:\n"
            "    qs = OrganizationMembership.objects.all()\n\n"
            "    def owners(self):\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, class_method_shadow) == []

    late_module_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    return qs.filter(role='owner')\n\n\n"
            "qs = OrganizationMembership.objects.all()\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, late_module_binding)
    )

    unrelated_direct = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from another_app.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    return OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, unrelated_direct) == []

    named_model_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(OrganizationMembership):\n"
            "    return OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, named_model_shadow) == []

    comprehension_walrus = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(users):\n"
            "    rows = [\n"
            "        (qs := OrganizationMembership.objects.filter(user=user)) for user in users\n"
            "    ]\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, comprehension_walrus)
    )

    role_member = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrgRole, OrganizationMembership\n\n\n"
            "def owners():\n"
            "    return OrganizationMembership.objects.filter(role=OrgRole.OWNER)\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, role_member) == []

    orgs = _with_files(
        _golden_module("orgs"),
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    return OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, orgs) == []


def test_role_check_nonlocal_resolves_nearest_binding() -> None:
    """``nonlocal`` resolves the nearest enclosing binding, not any provenance."""
    module = _golden_module()
    nearest_without_provenance = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def outer():\n"
            "    qs = OrganizationMembership.objects.all()\n\n"
            "    def middle():\n"
            "        qs = Contact.objects.all()\n\n"
            "        def owners():\n"
            "            nonlocal qs\n"
            "            return qs.filter(role='owner')\n\n"
            "        return owners\n\n"
            "    return middle\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, nearest_without_provenance) == []

    nearest_parameter = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def outer():\n"
            "    qs = OrganizationMembership.objects.all()\n\n"
            "    def middle(qs):\n"
            "        def owners():\n"
            "            nonlocal qs\n"
            "            return qs.filter(role='owner')\n\n"
            "        return owners\n\n"
            "    return middle\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, nearest_parameter) == []

    nearest_with_provenance = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def outer():\n"
            "    def middle():\n"
            "        qs = OrganizationMembership.objects.all()\n\n"
            "        def owners():\n"
            "            nonlocal qs\n"
            "            return qs.filter(role='owner')\n\n"
            "        return owners\n\n"
            "    return middle\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, nearest_with_provenance)
    )

    default_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def outer():\n"
            "    qs = OrganizationMembership.objects.all()\n\n"
            "    def middle():\n"
            "        def capture(value=(qs := Contact.objects.all())):\n"
            "            return value\n\n"
            "        def owners():\n"
            "            nonlocal qs\n"
            "            return qs.filter(role='owner')\n\n"
            "        return owners\n\n"
            "    return middle\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, default_binding) == []

    default_binding_provenance = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def outer():\n"
            "    qs = Contact.objects.all()\n\n"
            "    def middle():\n"
            "        def capture(value=(qs := OrganizationMembership.objects.all())):\n"
            "            return value\n\n"
            "        def owners():\n"
            "            nonlocal qs\n"
            "            return qs.filter(role='owner')\n\n"
            "        return owners\n\n"
            "    return middle\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, default_binding_provenance)
    )


def test_role_check_finally_consumes_and_supersedes_state() -> None:
    """``finally`` sees every arrival's state and its output replaces them."""
    module = _golden_module()
    body_arrival = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    try:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, body_arrival)
    )

    handler_arrival = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    try:\n"
            "        raise ValueError('boom')\n"
            "    except ValueError:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, handler_arrival)
    )

    else_arrival = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    try:\n"
            "        pass\n"
            "    except ValueError:\n"
            "        pass\n"
            "    else:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, else_arrival)
    )

    finally_supersedes = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    try:\n"
            "        pass\n"
            "    finally:\n"
            "        qs = Contact.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, finally_supersedes) == []

    intermediate_exception = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    qs = Contact.objects.all()\n"
            "    try:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "        work()\n"
            "        qs = Contact.objects.all()\n"
            "    except ValueError:\n"
            "        pass\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, intermediate_exception)
    )

    nested_finally = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    qs = Contact.objects.all()\n"
            "    try:\n"
            "        try:\n"
            "            qs = OrganizationMembership.objects.all()\n"
            "            work()\n"
            "        finally:\n"
            "            qs = Contact.objects.all()\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, nested_finally) == []

    finally_exception = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    qs = Contact.objects.all()\n"
            "    try:\n"
            "        try:\n"
            "            pass\n"
            "        finally:\n"
            "            qs = OrganizationMembership.objects.all()\n"
            "            work()\n"
            "            qs = Contact.objects.all()\n"
            "    finally:\n"
            "        return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, finally_exception)
    )


def test_role_check_class_compound_method_scope() -> None:
    """A method in a class-body compound resolves the class's outer scope."""
    module = _golden_module()
    outer_membership = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "class Owners:\n"
            "    qs = Contact.objects.all()\n\n"
            "    if True:\n"
            "        def owners(self):\n"
            "            return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, outer_membership)
    )

    outer_contact = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n"
            "qs = Contact.objects.all()\n\n\n"
            "class Owners:\n"
            "    qs = OrganizationMembership.objects.all()\n\n"
            "    if True:\n"
            "        def owners(self):\n"
            "            return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, outer_contact) == []


def test_role_check_deferred_body_belongs_to_defining_scope() -> None:
    """A body defined in a compound waits for its real defining scope."""
    module = _golden_module()
    late_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners():\n"
            "    if True:\n"
            "        def check():\n"
            "            return qs.filter(role='owner')\n\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    return check\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, late_binding)
    )

    other_branch = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(flag):\n"
            "    qs = Contact.objects.all()\n"
            "    if flag:\n"
            "        def check():\n"
            "            return qs.filter(role='owner')\n"
            "    else:\n"
            "        qs = OrganizationMembership.objects.all()\n"
            "    return check\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, other_branch)
    )

    no_provenance = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    if True:\n"
            "        def check():\n"
            "            return qs.filter(role='owner')\n\n"
            "    qs = Contact.objects.all()\n"
            "    return check\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, no_provenance) == []


def test_role_check_resolves_qualified_module_aliases() -> None:
    """An alias of the orgs package or its models module resolves the model."""
    module = _golden_module()
    models_alias = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models as org_models\n\n\n"
            "def owners():\n"
            "    return org_models.OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, models_alias)
    )

    package_alias = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs as orgs\n\n\n"
            "def owners():\n"
            "    return orgs.models.OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, package_alias)
    )

    from_import_alias = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs import models as org_models\n\n\n"
            "def owners():\n"
            "    return org_models.OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, from_import_alias)
    )

    unrelated_attribute = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models as org_models\n\n\n"
            "def owners():\n"
            "    return org_models.Contact.objects.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, unrelated_attribute) == []

    shadowed_alias = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models as org_models\n"
            "from another_app.models import Contact\n\n\n"
            "def owners():\n"
            "    org_models = Contact.objects.all()\n"
            "    return org_models.OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, shadowed_alias) == []

    unaliased_package = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models\n\n\n"
            "def owners():\n"
            "    return quickscale_modules_orgs.models.OrganizationMembership.objects.filter(\n"
            "        role='owner'\n"
            "    )\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, unaliased_package)
    )

    parameter_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models\n\n\n"
            "def contacts(quickscale_modules_orgs):\n"
            "    return quickscale_modules_orgs.models.OrganizationMembership.objects.filter(\n"
            "        role='owner'\n"
            "    )\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, parameter_shadow) == []

    assignment_shadow = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "import quickscale_modules_orgs.models\n\n\n"
            "def contacts(item):\n"
            "    quickscale_modules_orgs = item\n"
            "    return quickscale_modules_orgs.models.OrganizationMembership.objects.filter(\n"
            "        role='owner'\n"
            "    )\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, assignment_shadow) == []

    joined_aliases = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "def owners(flag):\n"
            "    if flag:\n"
            "        import quickscale_modules_orgs.models as orgs\n"
            "    else:\n"
            "        import quickscale_modules_orgs as orgs\n"
            "    return orgs.OrganizationMembership.objects.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, joined_aliases)
    )


def test_role_check_match_capture_rebind() -> None:
    """A match capture re-bound to membership keeps its post-match provenance."""
    module = _golden_module()
    capture_then_rebind = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(payload):\n"
            "    match payload:\n"
            "        case {'queryset': qs}:\n"
            "            qs = OrganizationMembership.objects.all()\n"
            "        case _:\n"
            "            raise ValueError('unexpected payload')\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, capture_then_rebind)
    )

    capture_without_rebind = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n"
            "qs = OrganizationMembership.objects.all()\n\n\n"
            "def contacts(payload):\n"
            "    match payload:\n"
            "        case {'queryset': qs}:\n"
            "            pass\n"
            "        case _:\n"
            "            raise ValueError('unexpected payload')\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, capture_without_rebind) == []

    other_case_binding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(payload):\n"
            "    match payload:\n"
            "        case {'queryset': qs}:\n"
            "            pass\n"
            "        case _:\n"
            "            qs = OrganizationMembership.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, other_case_binding)
    )

    prebound_other_case = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(payload):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    match payload:\n"
            "        case {'queryset': qs}:\n"
            "            pass\n"
            "        case _:\n"
            "            qs = OrganizationMembership.objects.all()\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, prebound_other_case)
    )

    guard_rebinding = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(payload):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    match payload:\n"
            "        case {'queryset': qs}:\n"
            "            pass\n"
            "        case _ if (qs := OrganizationMembership.objects.all()).exists():\n"
            "            pass\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, guard_rebinding)
    )


def test_role_check_comprehension_walrus_retains_prestate() -> None:
    """A walrus in a comprehension may not run, so the pre-state stays."""
    module = _golden_module()
    zero_iteration = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    [qs := Contact.objects.get(pk=user.pk) for user in users]\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, zero_iteration)
    )

    established = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n\n\n"
            "def owners(users):\n"
            "    [qs := OrganizationMembership.objects.all() for _ in users]\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, established)
    )

    executing_iteration = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    return [\n"
            "        qs.filter(role='owner')\n"
            "        for user in users\n"
            "        if (qs := Contact.objects.all())\n"
            "    ]\n"
        ),
    )
    assert _violations(checker.rule_44_role_checks, executing_iteration) == []

    executing_iteration_provenance = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users):\n"
            "    qs = Contact.objects.all()\n"
            "    return [\n"
            "        qs.filter(role='owner')\n"
            "        for user in users\n"
            "        if (qs := OrganizationMembership.objects.all())\n"
            "    ]\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, executing_iteration_provenance)
    )

    short_circuited = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users, flag):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    return [\n"
            "        qs.filter(role='owner')\n"
            "        for user in users\n"
            "        if flag or (qs := Contact.objects.all())\n"
            "    ]\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, short_circuited)
    )

    nested_short_circuit = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users, flag):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    return [\n"
            "        qs.filter(role='owner')\n"
            "        for user in users\n"
            "        if flag or (value := (qs := Contact.objects.all()))\n"
            "    ]\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, nested_short_circuit)
    )

    nested_comprehension = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            "from quickscale_modules_orgs.models import OrganizationMembership\n"
            "from another_app.models import Contact\n\n\n"
            "def owners(users):\n"
            "    qs = OrganizationMembership.objects.all()\n"
            "    rows = [\n"
            "        [(qs := Contact.objects.get(pk=user.pk)) for _ in range(1)]\n"
            "        for user in users\n"
            "    ]\n"
            "    return qs.filter(role='owner')\n"
        ),
    )
    assert any(
        "filters OrganizationMembership by string role 'owner' outside orgs" in violation
        for violation in _violations(checker.rule_44_role_checks, nested_comprehension)
    )
