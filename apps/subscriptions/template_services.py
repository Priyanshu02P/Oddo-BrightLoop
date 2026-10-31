"""Admin-only quotation template writes (FR-4.1)."""

import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.audit import record_audit
from apps.accounts.permissions import Permission, has_permission

from .exceptions import InvalidLine, StaleTemplateLines
from .models import QuotationTemplate, QuotationTemplateLine

logger = logging.getLogger(__name__)

TEMPLATE_FIELDS = ("name", "plan", "validity_days")
LINE_FIELDS = ("product", "variant", "quantity", "is_addon")


def _require_template_admin(actor):
    # Checked here as well as in the views: Staff may use templates, never manage them.
    if not has_permission(actor, Permission.MANAGE_QUOTATION_TEMPLATES):
        raise PermissionDenied


def _apply(instance, data, names):
    for name in names:
        setattr(instance, name, data[name])
    instance.full_clean()
    instance.save()


def _sync_lines(template, lines):
    """Make the template's lines match `lines` exactly (same contract as the
    catalog variant sync): rows with an id update that line, rows without
    create one, lines not listed are removed."""
    existing = {line.pk: line for line in template.lines.all()}
    kept = set()
    for row in lines:
        line_id = row.get("id")
        if line_id is None:
            line = QuotationTemplateLine(template=template)
        elif line_id in existing:
            line = existing[line_id]
            kept.add(line_id)
        else:
            raise StaleTemplateLines(
                "The lines of this template were changed by someone else. "
                "Reload the page and try again."
            )
        if row["product"].is_archived:
            raise InvalidLine(f"“{row['product'].name}” is archived and can't be used on a line.")
        _apply(line, row, LINE_FIELDS)
    QuotationTemplateLine.objects.filter(pk__in=set(existing) - kept).delete()


def create_quotation_template(*, actor, fields, lines):
    _require_template_admin(actor)
    with transaction.atomic():
        template = QuotationTemplate()
        _apply(template, fields, TEMPLATE_FIELDS)
        _sync_lines(template, lines)
        record_audit(actor=actor, action="quotation_template.created", target=template)
    logger.info("Quotation template %s created by user %s", template.pk, actor.pk)
    return template


def update_quotation_template(*, actor, template, fields, lines):
    """Only the template changes; subscriptions made from it keep their own
    copied lines (FR-4.2)."""
    _require_template_admin(actor)
    with transaction.atomic():
        template = QuotationTemplate.objects.select_for_update().get(pk=template.pk)
        _apply(template, fields, TEMPLATE_FIELDS)
        _sync_lines(template, lines)
        record_audit(actor=actor, action="quotation_template.updated", target=template)
    logger.info("Quotation template %s updated by user %s", template.pk, actor.pk)
    return template
