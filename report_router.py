"""
FastAPI router for automated reporting engine with AI summaries.
"""

import csv
import logging
import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Optional

try:
    import boto3
except ImportError:
    boto3 = None
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

try:
    from weasyprint import HTML
except ImportError:
    HTML = None

from auth import get_current_user
from database import get_db
from models import ReportDelivery, ReportTemplate, ScheduledReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])


class FrequencyEnum(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class ReportConfig(BaseModel):
    queries: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    include_ai_summary: bool = True
    include_csv_export: bool = True


class ReportTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    config: ReportConfig


class ReportTemplateResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    config: ReportConfig
    created_at: str
    updated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ScheduledReportCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_id: Optional[str] = None
    frequency: FrequencyEnum
    time_of_day: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    timezone: str = Field(default="UTC", max_length=50)
    recipients: list[str] = Field(..., min_length=1)
    config: ReportConfig

    @field_validator("recipients")
    @classmethod
    def validate_recipients(cls, v):
        for email in v:
            if "@" not in email:
                raise ValueError(f"Invalid email: {email}")
        return v


class ScheduledReportUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: Optional[FrequencyEnum] = None
    time_of_day: Optional[str] = Field(None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$")
    timezone: Optional[str] = Field(None, max_length=50)
    recipients: Optional[list[str]] = None
    config: Optional[ReportConfig] = None
    is_active: Optional[bool] = None


class ScheduledReportResponse(BaseModel):
    id: str
    user_id: str
    template_id: Optional[str]
    name: str
    description: Optional[str]
    frequency: str
    time_of_day: str
    timezone: str
    recipients: list[str]
    is_active: bool
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    config: ReportConfig
    created_at: str
    updated_at: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ReportDeliveryResponse(BaseModel):
    id: str
    scheduled_report_id: str
    status: str
    delivered_at: Optional[str]
    error_message: Optional[str]
    pdf_url: Optional[str]
    csv_urls: list[str]
    ai_summary: Optional[str]
    metadata: Optional[dict[str, Any]]
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class AIQuerySummaryRequest(BaseModel):
    query_results: list[dict[str, Any]]
    query_description: str = Field(..., min_length=1)


class AIQuerySummaryResponse(BaseModel):
    summary: str
    key_insights: list[str]
    recommendations: list[str]


class ReportPreviewRequest(BaseModel):
    config: ReportConfig
    preview_type: str = Field(default="pdf", pattern=r"^(pdf|html)$")


class DeliveryStatusUpdate(BaseModel):
    status: str = Field(..., pattern=r"^(pending|sent|failed|bounced)$")
    error_message: Optional[str] = None


def calculate_next_run(
    frequency: str, time_of_day: str, timezone: str = "UTC"
) -> datetime:
    now = datetime.now(dt_timezone.utc)
    hour, minute = map(int, time_of_day.split(":"))
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    if frequency == "weekly":
        days_ahead = 0
        while next_run <= now or days_ahead < 7:
            if next_run > now:
                break
            next_run += timedelta(days=1)
            days_ahead += 1
        if next_run <= now:
            next_run += timedelta(days=7)
    elif frequency == "monthly":
        if next_run <= now:
            if now.month == 12:
                next_run = next_run.replace(year=now.year + 1, month=1)
            else:
                next_run = next_run.replace(month=now.month + 1)
    return next_run


@router.post("/templates", response_model=ReportTemplateResponse)
async def create_report_template(
    data: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    template = ReportTemplate(
        user_id=str(current_user.id),
        name=data.name,
        description=data.description,
        config=data.config.model_dump(),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[ReportTemplateResponse])
async def list_report_templates(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    templates = (
        db.query(ReportTemplate)
        .filter(ReportTemplate.user_id == str(current_user.id))
        .order_by(ReportTemplate.created_at.desc())
        .all()
    )
    return templates


@router.get("/templates/{template_id}", response_model=ReportTemplateResponse)
async def get_report_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    template = (
        db.query(ReportTemplate)
        .filter(
            ReportTemplate.id == template_id,
            ReportTemplate.user_id == str(current_user.id),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/templates/{template_id}", response_model=ReportTemplateResponse)
async def update_report_template(
    template_id: str,
    data: ReportTemplateCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    template = (
        db.query(ReportTemplate)
        .filter(
            ReportTemplate.id == template_id,
            ReportTemplate.user_id == str(current_user.id),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.name = data.name
    template.description = data.description
    template.config = data.config.model_dump()
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}")
async def delete_report_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    template = (
        db.query(ReportTemplate)
        .filter(
            ReportTemplate.id == template_id,
            ReportTemplate.user_id == str(current_user.id),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"detail": "Template deleted"}


@router.post("/scheduled", response_model=ScheduledReportResponse)
async def create_scheduled_report(
    data: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    next_run = calculate_next_run(data.frequency, data.time_of_day, data.timezone)
    report = ScheduledReport(
        user_id=str(current_user.id),
        template_id=data.template_id,
        name=data.name,
        description=data.description,
        frequency=data.frequency,
        time_of_day=data.time_of_day,
        timezone=data.timezone,
        recipients=data.recipients,
        is_active=True,
        next_run_at=next_run,
        config=data.config.model_dump(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/scheduled", response_model=list[ScheduledReportResponse])
async def list_scheduled_reports(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = db.query(ScheduledReport).filter(
        ScheduledReport.user_id == str(current_user.id)
    )
    if is_active is not None:
        query = query.filter(ScheduledReport.is_active == is_active)
    reports = query.order_by(ScheduledReport.next_run_at.asc()).all()
    return reports


@router.get("/scheduled/{report_id}", response_model=ScheduledReportResponse)
async def get_scheduled_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    return report


@router.put("/scheduled/{report_id}", response_model=ScheduledReportResponse)
async def update_scheduled_report(
    report_id: str,
    data: ScheduledReportUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    if data.name is not None:
        report.name = data.name
    if data.description is not None:
        report.description = data.description
    if data.frequency is not None:
        report.frequency = data.frequency
    if data.time_of_day is not None:
        report.time_of_day = data.time_of_day
    if data.timezone is not None:
        report.timezone = data.timezone
    if data.recipients is not None:
        report.recipients = data.recipients
    if data.config is not None:
        report.config = data.config.model_dump()
    if data.is_active is not None:
        report.is_active = data.is_active
    if data.frequency or data.time_of_day:
        report.next_run_at = calculate_next_run(
            report.frequency, report.time_of_day, report.timezone
        )
    db.commit()
    db.refresh(report)
    return report


@router.post("/scheduled/{report_id}/pause")
async def pause_scheduled_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    report.is_active = False
    db.commit()
    return {"detail": "Report paused"}


@router.post("/scheduled/{report_id}/resume")
async def resume_scheduled_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    report.is_active = True
    report.next_run_at = calculate_next_run(
        report.frequency, report.time_of_day, report.timezone
    )
    db.commit()
    return {"detail": "Report resumed"}


@router.delete("/scheduled/{report_id}")
async def delete_scheduled_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    db.delete(report)
    db.commit()
    return {"detail": "Scheduled report deleted"}


@router.post("/scheduled/{report_id}/run", response_model=ReportDeliveryResponse)
async def run_scheduled_report(
    report_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    report = (
        db.query(ScheduledReport)
        .filter(
            ScheduledReport.id == report_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    delivery = ReportDelivery(
        scheduled_report_id=report.id,
        status="pending",
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    background_tasks.add_task(generate_report, report.id, delivery.id, db)
    return delivery


@router.get("/deliveries", response_model=list[ReportDeliveryResponse])
async def list_report_deliveries(
    report_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = (
        db.query(ReportDelivery)
        .join(ScheduledReport)
        .filter(ScheduledReport.user_id == str(current_user.id))
    )
    if report_id:
        query = query.filter(ReportDelivery.scheduled_report_id == report_id)
    if status:
        query = query.filter(ReportDelivery.status == status)
    deliveries = query.order_by(ReportDelivery.created_at.desc()).all()
    return deliveries


@router.get("/deliveries/{delivery_id}", response_model=ReportDeliveryResponse)
async def get_report_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delivery = (
        db.query(ReportDelivery)
        .join(ScheduledReport)
        .filter(
            ReportDelivery.id == delivery_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    return delivery


@router.put("/deliveries/{delivery_id}/status")
async def update_delivery_status(
    delivery_id: str,
    data: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delivery = (
        db.query(ReportDelivery)
        .join(ScheduledReport)
        .filter(
            ReportDelivery.id == delivery_id,
            ScheduledReport.user_id == str(current_user.id),
        )
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    delivery.status = data.status
    if data.error_message:
        delivery.error_message = data.error_message
    if data.status in ["sent", "bounced"]:
        delivery.delivered_at = datetime.now(dt_timezone.utc)
    db.commit()
    return {"detail": "Delivery status updated"}


@router.post("/ai-summary", response_model=AIQuerySummaryResponse)
async def generate_ai_summary(
    data: AIQuerySummaryRequest,
    current_user=Depends(get_current_user),
):
    summary, insights, recommendations = generate_ai_summary_from_results(
        data.query_results, data.query_description
    )
    return AIQuerySummaryResponse(
        summary=summary,
        key_insights=insights,
        recommendations=recommendations,
    )


@router.post("/preview")
async def preview_report(
    data: ReportPreviewRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    html_content = generate_report_html(
        data.config.model_dump(), str(current_user.id), db
    )
    if data.preview_type == "html":
        return {"html": html_content}
    return {"detail": "PDF preview not yet implemented, use HTML", "html": html_content}


def generate_ai_summary_from_results(
    results: list[dict[str, Any]], description: str
) -> tuple[str, list[str], list[str]]:
    row_count = len(results)
    if row_count == 0:
        return (
            f"No data found for {description}.",
            ["No records returned"],
            ["Check data sources and filters"],
        )
    columns = list(results[0].keys()) if results else []
    summary = f"Query '{description}' returned {row_count} rows with columns: {', '.join(columns[:5])}."
    if row_count > 0:
        summary += f" The first result shows {columns[0]}={results[0].get(columns[0])}."
    insights = [
        f"Total of {row_count} records analyzed",
        f"Data includes {len(columns)} columns",
        f"Most recent entry: {results[0] if results else 'N/A'}",
    ]
    recommendations = [
        "Review the data for anomalies or outliers",
        "Consider segmenting the data for deeper insights",
        "Compare with historical trends if available",
    ]
    return summary, insights[:3], recommendations[:3]


def generate_report_html(config: dict, user_id: str, db: Session) -> str:
    """Generate HTML report with actual data."""
    queries = config.get("queries", [])
    charts = config.get("charts", [])
    html = """<html>
<head>
    <title>Automated Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #2c3e50; }
        h2 { color: #34495e; margin-top: 30px; }
        h3 { color: #7f8c8d; }
        table { border-collapse: collapse; width: 100%; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .summary { background: #f8f9fa; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>"""
    html += "<h1>Automated Report</h1>"
    html += f"<p>Generated at: {datetime.now(dt_timezone.utc).isoformat()}</p>"

    if queries:
        html += "<h2>Query Results</h2>"
        for q in queries:
            html += f"<h3>{q.get('description', 'Query')}</h3>"
            sql = q.get("sql")
            if sql and db:
                try:
                    result = db.execute(sql)
                    rows = [dict(r) for r in result]
                    if rows:
                        html += "<table><tr>"
                        for col in rows[0].keys():
                            html += f"<th>{col}</th>"
                        html += "</tr>"
                        for row in rows[:100]:  # Limit to 100 rows
                            html += "<tr>"
                            for val in row.values():
                                html += f"<td>{val}</td>"
                            html += "</tr>"
                        html += "</table>"
                        html += f"<p><em>Showing {len(rows[:100])} of {len(rows)} rows</em></p>"
                    else:
                        html += "<p>No results found.</p>"
                except Exception as e:
                    html += f"<p>Error executing query: {str(e)}</p>"

    if charts:
        html += "<h2>Charts</h2>"
        for c in charts:
            html += f"<h3>{c.get('title', 'Chart')}</h3>"
            html += "<p>Chart visualization would be rendered here.</p>"

    html += "</body></html>"
    return html


def generate_report_pdf(html_content: str, output_path: str) -> str:
    """Generate PDF from HTML using weasyprint."""
    if HTML is None:
        raise ImportError("weasyprint is not installed")
    try:
        HTML(string=html_content).write_pdf(output_path)
        return output_path
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise


def generate_csv_export(query_results: list[dict], output_path: str) -> str:
    """Generate CSV file from query results."""
    if not query_results:
        return ""
    try:
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=query_results[0].keys())
            writer.writeheader()
            writer.writerows(query_results)
        return output_path
    except Exception as e:
        logger.error(f"CSV generation failed: {e}")
        raise


async def send_email_ses(
    recipients: list[str],
    subject: str,
    html_body: str,
    attachment_urls: list[str] = None,
) -> bool:
    """Send email via AWS SES."""
    if not boto3:
        logger.warning("boto3 not available, skipping email send")
        return False
    try:
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        ses_client = boto3.client("ses", region_name=aws_region)

        body = {"Html": {"Data": html_body, "Charset": "UTF-8"}}

        response = ses_client.send_email(
            Source=os.getenv("SES_SENDER_EMAIL", "noreply@example.com"),
            Destination={"ToAddresses": recipients},
            Message={"Subject": {"Data": subject}, "Body": body},
        )
        logger.info(f"Email sent: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        return False


async def generate_report(report_id: str, delivery_id: str, db: Session):
    """Generate and deliver a scheduled report."""
    import os

    report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
    delivery = db.query(ReportDelivery).filter(ReportDelivery.id == delivery_id).first()
    if not report or not delivery:
        return

    try:
        config = report.config
        user_id = report.user_id
        queries = config.get("queries", [])
        all_results = []

        # Execute queries and collect results
        for q in queries:
            sql = q.get("sql")
            if sql:
                try:
                    result = db.execute(sql)
                    rows = [dict(r) for r in result]
                    all_results.extend(rows)
                except Exception as e:
                    logger.warning(f"Query execution failed: {e}")

        # Generate AI summary
        ai_summary = ""
        if config.get("include_ai_summary", True):
            summary, insights, recommendations = generate_ai_summary_from_results(
                all_results, "report query"
            )
            ai_summary = f"{summary}\n\nKey Insights:\n" + "\n".join(
                f"- {i}" for i in insights
            )

        # Generate HTML report
        html_content = generate_report_html(config, user_id, db)

        # Generate PDF
        pdf_url = None
        if config.get("include_pdf", True):
            pdf_path = f"/tmp/report_{delivery_id}.pdf"
            try:
                generate_report_pdf(html_content, pdf_path)
                pdf_url = pdf_path
                # Upload to S3 if configured and boto3 is available
                if boto3:
                    s3_bucket = os.getenv("REPORT_S3_BUCKET")
                    if s3_bucket:
                        s3_key = f"reports/{report_id}/{delivery_id}.pdf"
                        s3 = boto3.client("s3")
                        s3.upload_file(pdf_path, s3_bucket, s3_key)
                        pdf_url = f"s3://{s3_bucket}/{s3_key}"
            except Exception as e:
                logger.error(f"PDF generation failed: {e}")

        # Generate CSV exports
        csv_urls = []
        if config.get("include_csv_export", True):
            for i, q in enumerate(queries):
                if q.get("sql"):
                    csv_path = f"/tmp/report_{delivery_id}_query_{i}.csv"
                    try:
                        generate_csv_export(all_results, csv_path)
                        csv_urls.append(csv_path)
                    except Exception as e:
                        logger.error(f"CSV generation failed: {e}")

        # Update delivery record
        delivery.status = "sent"
        delivery.delivered_at = datetime.now(dt_timezone.utc)
        delivery.pdf_url = pdf_url
        delivery.csv_urls = csv_urls
        delivery.ai_summary = ai_summary

        # Update report schedule
        report.last_run_at = datetime.now(dt_timezone.utc)
        report.next_run_at = calculate_next_run(
            report.frequency, report.time_of_day, report.timezone
        )

        db.commit()

        # Send email
        if report.recipients:
            subject = f"Report: {report.name}"
            await send_email_ses(
                recipients=report.recipients,
                subject=subject,
                html_body=html_content,
            )

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        delivery.status = "failed"
        delivery.error_message = str(e)
        db.commit()
