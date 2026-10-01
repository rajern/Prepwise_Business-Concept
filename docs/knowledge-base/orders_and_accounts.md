# Orders and Accounts

Customers need an account to place an order.

After checkout, the order is saved to the customer's account.

Order status follows the standard flow:

**Received → Preparing → Ready for pickup → Completed**

Customers can view active upcoming orders above the meal menu after signing in. Completed and
cancelled orders are available through Order history in the top navigation. Passing the pickup
time does not automatically mark an uncollected order completed.

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

Customers cannot view or manage another customer's orders.

