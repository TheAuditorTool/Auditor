import { NextResponse } from "next/server";

const rateLimitStore = new Map();

function checkRateLimit(ip, limit = 100, windowMs = 60000) {
  const now = Date.now();
  const key = `rate_limit:${ip}`;

  if (!rateLimitStore.has(key)) {
    rateLimitStore.set(key, { count: 1, resetTime: now + windowMs });
    return { allowed: true, remaining: limit - 1 };
  }

  const record = rateLimitStore.get(key);

  if (now > record.resetTime) {
    rateLimitStore.set(key, { count: 1, resetTime: now + windowMs });
    return { allowed: true, remaining: limit - 1 };
  }

  if (record.count >= limit) {
    return { allowed: false, remaining: 0, resetTime: record.resetTime };
  }

  record.count++;
  rateLimitStore.set(key, record);
  return { allowed: true, remaining: limit - record.count };
}

export function middleware(request) {
  const { pathname, searchParams } = request.nextUrl;

  const ip = request.ip || request.headers.get("x-forwarded-for") || "unknown";

  const userAgent = request.headers.get("user-agent") || "";

  if (pathname.startsWith("/api/")) {
    const { allowed, remaining, resetTime } = checkRateLimit(ip, 100, 60000);

    if (!allowed) {
      return NextResponse.json(
        {
          error: "Too many requests",
          retryAfter: Math.ceil((resetTime - Date.now()) / 1000),
        },
        {
          status: 429,
          headers: {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": new Date(resetTime).toISOString(),
            "Retry-After": String(Math.ceil((resetTime - Date.now()) / 1000)),
          },
        },
      );
    }

    const response = NextResponse.next();
    response.headers.set("X-RateLimit-Limit", "100");
    response.headers.set("X-RateLimit-Remaining", String(remaining));
    return response;
  }

  if (
    userAgent.toLowerCase().includes("bot") &&
    !userAgent.toLowerCase().includes("googlebot")
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const response = NextResponse.next();
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");

  return response;
}

export const config = {
  matcher: ["/api/:path*", "/((?!_next/static|_next/image|favicon.ico).*)"],
};
