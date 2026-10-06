# Orders and Accounts

Customers need an account to place an order.

After checkout, the order is saved to the customer's account.

Order status follows the standard flow:

**Received → Preparing → Ready for pickup → Completed**

Customers can view upcoming orders above the meal menu after signing in until the pickup
window ends. Completed and cancelled orders, and orders whose pickup window has ended, are
available through Order history in the top navigation. An elapsed window does not prove
collection: an uncollected order keeps its actual status and is labelled as past pickup.

## Can I cancel or change an order?

Use the Cancel order button and confirm on the website. Cancellation is allowed until midnight
before the pickup day, in Europe/Oslo, never on the pickup day itself. The API enforces the deadline.
Completed and cancelled orders cannot be cancelled. Cancelled orders remain in history.
Pickup date, time and location cannot be edited after checkout: cancel within the deadline and
place a new order instead. There is no payment/refund workflow in this portfolio demo.

## Can I order for different pickup days?

Create separate pickup groups in the cart, select each group's location, date and time, and move
meals into the appropriate group. Each group becomes a separate order; checking out one group
leaves the others in the cart. Complete pickup choices are saved and editable before checkout.
Chat cart additions go to unassigned meals; review multi-group checkout through the website.

## What if checkout or chat fails?

Checkout first shows a server review of the selected meals, prices, pickup location and time.
If that information changes before confirmation, review it again. If a checkout response is
lost, use Check previous checkout to retry the same reference; an existing order is returned
without creating another order or consuming newer cart items. An authentication error alone
does not prove that an earlier checkout failed.

If chat reports an uncertain or applied action, inspect the cart and orders before sending
another request. Retrying the exact failed message retains its original reference. A message
that may have changed state is not automatically executed again. Starting a new chat or
phrasing the same action differently does not undo an earlier action.

Customers cannot view or manage another customer's orders.

