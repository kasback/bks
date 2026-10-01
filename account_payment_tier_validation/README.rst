=======================
Payment Tier Validation
=======================

This module extends Payments (``account.payment``) with the
``base_tier_validation`` workflow already used in the ``bks`` addons.

A payment that matches a *Tier Definition* cannot be confirmed until all
required reviews are approved.

Installation
============

Install **Payment Tier Validation** after ``account`` and
``base_tier_validation``.

Configuration
=============

1. Go to *Settings > Technical > Tier Validations > Tier Definition*.
2. Create one or more definitions on the **Payments** model.

Typical examples:

* Vendor payments (``payment_type = outbound``) above a given amount
* Reviewer = a user or the Accounting Manager group
* Sequential reviews (manager, then director)

Usage
=====

1. Create a draft payment that matches a tier definition.
2. Click **Request Validation**.
3. Reviewers approve or reject from the payment form or the review menu.
4. Once the status is **Validated**, click **Confirm**.

A reviewer who can approve every required tier may confirm the payment
directly.

Payments created from an invoice via **Register Payment** stay in draft
and request validation when a tier applies.

Filters
=======

The payment search view adds:

* **Needs my Review**
* **No Validation Requested**
* **Validation In Progress**
* **Validated**
