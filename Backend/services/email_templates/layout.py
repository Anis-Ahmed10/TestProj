"""Shared HTML email chrome (header/footer) matching the Infuse Platform theme.

Table-based layout with inline styles only (no external CSS/fonts/images) so it
renders consistently — and without blocked assets — across email clients like
Outlook and the Gmail app.
"""

from __future__ import annotations

FONT_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def render_email_layout(body_rows_html: str) -> str:
    """Wrap templated `<tr>` rows in the shared header/footer chrome.

    `body_rows_html` must be one or more `<tr>...</tr>` blocks — the caller
    supplies the email-specific content, this supplies everything around it.
    """
    return f"""\
<html>
  <body style="margin:0; padding:0; background-color:#f3f4f6;
    font-family:{FONT_STACK};">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
      border="0" style="background-color:#f3f4f6; padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
            border="0" style="max-width:480px; width:100%; background-color:#ffffff;
            border-radius:12px; overflow:hidden; border:1px solid #e5e7eb;">
            <tr>
              <td style="background-color:#1f3333; padding:20px 28px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="width:36px; height:36px; border-radius:9px;
                      background-color:#ea580c; text-align:center; vertical-align:middle;">
                      <span style="font-size:12px; font-weight:800; color:#ffffff;
                        letter-spacing:-0.5px;">AI</span>
                    </td>
                    <td style="padding-left:12px;">
                      <div style="font-size:14px; font-weight:700; color:#ffffff;
                        line-height:1.2;">Infuse Platform</div>
                      <div style="font-size:10px; color:rgba(255,255,255,0.55);
                        line-height:1.2; margin-top:2px;">AI Testing Delivery</div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            {body_rows_html}
            <tr>
              <td style="padding:16px 28px; border-top:1px solid #e5e7eb;">
                <p style="margin:0; font-size:12px; color:#9ca3af;">
                  This is an automated notification from Infuse Platform.
                  Please do not reply to this email.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>\
"""
