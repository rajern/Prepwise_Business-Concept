# Prepwise — Product

## Purpose

Prepwise is a business concept for a meal-prep ordering service in Oslo.

The product is built as a realistic small production application. Its primary purpose is to provide hands-on experience with production software engineering and, later, production AI.

Business validation, pricing strategy and market viability are outside the scope of this project.

## Target user

Health- and fitness-conscious people who want to save time on cooking while still being able to make informed choices based on:

* calories
* macronutrients
* ingredients
* allergens
* price

## Core problem

Meal prep should make convenient food easier without removing transparency around nutrition and ingredients.

Prepwise allows users to browse ready-made meals, select what fits their needs and place an order for pickup.

## Customer flow

The main customer journey is:

`browse meals → sign up / log in → add to cart → open cart → choose pickup location/date/window → checkout → view order`

Users can:

* browse available meals without logging in
* view price, ingredients, allergens and nutritional information
* create an account and log in
* maintain a persistent shopping cart
* choose from multiple pickup locations in Oslo
* choose a pickup date and time window
* place an order without real payment processing
* view previous orders and order details
* see the current status of an order

## Meal information

Each meal should include:

* name
* description
* image
* price
* calories
* protein
* carbohydrates
* fat
* ingredients
* allergens
* availability

The service should have a small realistic menu, approximately 10–15 meals.

Individual meal customisation is not part of the MVP.

## Pickup

Orders are collected from predefined pickup locations in Oslo.

The MVP supports multiple pickup locations but no home delivery, route planning or delivery logistics.

The post-Milestone 2 flow offers the next five calendar days beginning tomorrow, including
weekends, with `16:00–18:00` and `18:00–20:00` windows in `Europe/Oslo`. The selected date and
window must appear consistently in checkout, confirmations, customer order history and admin.

## Customer language and assistance

Norwegian is the default customer language, with an explicit Norwegian/English switch.
Meal names, descriptions, ingredients and allergens follow that choice. Admin remains English.

A cart button in the top navigation opens a side panel and displays the current quantity.
Adding an item gives a brief confirmation without automatically scrolling the page.

A floating assistant button is visible to guests, while sending messages requires sign-in.
The conversation is retained only in the current tab and cleared on logout. Assistant cart
changes are reflected without a full page refresh.

## Orders

Checkout creates a real order in the application database.

No real payment provider is required for Milestone 1.

Orders have a simple lifecycle, for example:

`received → preparing → ready for pickup → completed`

## Admin

Prepwise includes a small internal admin interface for employees.

Admins can:

* create and edit meals
* change meal availability
* manage pickup locations
* view orders
* update order status

The admin interface is an operational tool, not a separate full product.

## Milestone 1 scope

Milestone 1 is the complete non-AI product:

* customer-facing web application
* authentication
* meal catalogue
* persistent cart
* pickup selection
* checkout
* order history
* order status
* admin interface

The production engineering requirements for Milestone 1 are defined in `ARCHITECTURE.md`.

## Milestone 2 scope

Milestone 2 adds an AI assistant on top of the existing product.

The assistant may help users:

* find meals matching nutritional constraints
* answer questions about meals and the service
* inspect their cart and orders
* perform controlled actions such as adding meals to the cart

The AI architecture is defined in `ARCHITECTURE.md`.

## Non-goals

The following are intentionally outside Milestone 1:

* real payment processing
* subscriptions or recurring orders
* home delivery
* route optimisation
* advanced inventory or kitchen management
* discount codes
* reviews
* favourites
* social features
* push notifications
* personalised recommendation systems
* AI functionality

These features should not be added unless the project scope is explicitly changed.
