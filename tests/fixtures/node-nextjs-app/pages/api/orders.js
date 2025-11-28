import { createOrder, getUserActivity, logActivity } from "../../lib/database";

function requireAuth(handler) {
  return async (req, res) => {
    const token = req.headers.authorization?.replace("Bearer ", "");

    if (!token) {
      return res.status(401).json({ error: "Authentication required" });
    }

    try {
      const decoded = verifyToken(token);
      req.user = decoded;
      return handler(req, res);
    } catch (err) {
      return res.status(401).json({ error: "Invalid token" });
    }
  };
}

async function createOrderHandler(req, res) {
  const { items } = req.body;

  if (!items || !Array.isArray(items) || items.length === 0) {
    return res.status(400).json({ error: "Items are required" });
  }

  for (const item of items) {
    if (!item.productId || !item.quantity || !item.price) {
      return res.status(400).json({ error: "Invalid item format" });
    }
  }

  try {
    const { orderId, totalAmount } = await createOrder(req.user.id, items);

    await logActivity(
      req.user.id,
      "create_order",
      `Created order ${orderId} with ${items.length} items`,
    );

    return res.status(201).json({
      orderId,
      totalAmount,
      itemCount: items.length,
      message: "Order created successfully",
    });
  } catch (err) {
    console.error("Error creating order:", err);
    return res.status(500).json({ error: "Failed to create order" });
  }
}

async function getOrdersHandler(req, res) {
  const { limit = 50 } = req.query;

  try {
    const activity = await getUserActivity(req.user.id, parseInt(limit));

    const orderActivity = activity.filter(
      (a) =>
        a.action.startsWith("create_order") ||
        a.action.startsWith("update_order"),
    );

    return res.status(200).json({
      orders: orderActivity,
      total: orderActivity.length,
    });
  } catch (err) {
    console.error("Error fetching orders:", err);
    return res.status(500).json({ error: "Failed to fetch orders" });
  }
}

export default requireAuth(async function handler(req, res) {
  switch (req.method) {
    case "POST":
      return createOrderHandler(req, res);
    case "GET":
      return getOrdersHandler(req, res);
    default:
      return res.status(405).json({ error: "Method not allowed" });
  }
});

function verifyToken(token) {
  try {
    const payload = JSON.parse(
      Buffer.from(token.split(".")[1], "base64").toString(),
    );
    return payload;
  } catch (err) {
    throw new Error("Invalid token");
  }
}
