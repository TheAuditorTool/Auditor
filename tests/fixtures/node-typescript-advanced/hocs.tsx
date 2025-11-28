import React, { ComponentType, lazy, Suspense } from "react";

interface BaseComponentProps {
  title: string;
  content?: string;
}

const BaseComponent: React.FC<BaseComponentProps> = ({ title, content }) => {
  return (
    <div>
      <h1>{title}</h1>
      <p>{content}</p>
    </div>
  );
};

const UserProfile: React.FC<{ userId: number }> = ({ userId }) => {
  return <div>User {userId}</div>;
};

function withAuth<P extends object>(
  Component: ComponentType<P>,
): ComponentType<P> {
  return (props: P) => {
    const isAuthenticated = true;

    if (!isAuthenticated) {
      return <div>Please log in</div>;
    }

    return <Component {...props} />;
  };
}

interface WithLayoutProps {
  layoutType?: "default" | "sidebar" | "fullscreen";
}

function withLayout<P extends object>(
  Component: ComponentType<P>,
): ComponentType<P & WithLayoutProps> {
  return ({ layoutType = "default", ...props }: P & WithLayoutProps) => {
    return (
      <div className={`layout-${layoutType}`}>
        <header>Header</header>
        <main>
          <Component {...(props as P)} />
        </main>
        <footer>Footer</footer>
      </div>
    );
  };
}

function withLogging<P extends object>(
  Component: ComponentType<P>,
): ComponentType<P> {
  return (props: P) => {
    React.useEffect(() => {
      console.log(`Component mounted with props:`, props);
      return () => console.log(`Component unmounting`);
    }, [props]);

    return <Component {...props} />;
  };
}

function withErrorBoundary<P extends object>(
  Component: ComponentType<P>,
): ComponentType<P> {
  return class ErrorBoundary extends React.Component<P, { hasError: boolean }> {
    state = { hasError: false };

    static getDerivedStateFromError() {
      return { hasError: true };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
      console.error("Error caught:", error, errorInfo);
    }

    render() {
      if (this.state.hasError) {
        return <div>Something went wrong</div>;
      }
      return <Component {...this.props} />;
    }
  };
}

interface WithDataProps<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

function withData<P extends object, T = any>(
  fetcher: () => Promise<T>,
): (Component: ComponentType<P & WithDataProps<T>>) => ComponentType<P> {
  return (Component) => {
    return (props: P) => {
      const [data, setData] = React.useState<T | null>(null);
      const [loading, setLoading] = React.useState(true);
      const [error, setError] = React.useState<Error | null>(null);

      React.useEffect(() => {
        fetcher()
          .then(setData)
          .catch(setError)
          .finally(() => setLoading(false));
      }, []);

      return (
        <Component {...props} data={data} loading={loading} error={error} />
      );
    };
  };
}

const AuthenticatedLayout = withAuth(withLayout(BaseComponent));

const LoggedAuthComponent = withLogging(withAuth(BaseComponent));

const TripleWrappedComponent = withAuth(withLayout(withLogging(BaseComponent)));

const QuadrupleWrappedComponent = withAuth(
  withLayout(withLogging(withErrorBoundary(BaseComponent))),
);

const ExtremelyWrappedComponent = withErrorBoundary(
  withAuth(
    withLayout(
      withLogging(
        withData<BaseComponentProps, any>(() =>
          Promise.resolve({ data: "test" }),
        )(BaseComponent),
      ),
    ),
  ),
);

async function loadModule(moduleName: string): Promise<any> {
  const module = await import("./components/DynamicModule");
  return module.default;
}

async function loadConditionalModule(useAdmin: boolean): Promise<any> {
  if (useAdmin) {
    const adminModule = await import("./components/AdminModule");
    return adminModule.default;
  } else {
    const userModule = await import("./components/UserModule");
    return userModule.default;
  }
}

async function loadModuleSafely(moduleName: string): Promise<any> {
  try {
    const module = await import(`./components/${moduleName}`);
    return module.default;
  } catch (error) {
    console.error(`Failed to load module: ${moduleName}`, error);
    return null;
  }
}

async function loadMultipleModules(): Promise<any[]> {
  const [module1, module2, module3] = await Promise.all([
    import("./components/Module1"),
    import("./components/Module2"),
    import("./components/Module3"),
  ]);

  return [module1.default, module2.default, module3.default];
}

const LazyComponent = lazy(() => import("./components/LazyLoadedComponent"));

const LazyDashboard = lazy(() => import("./components/Dashboard"));
const LazySettings = lazy(() => import("./components/Settings"));
const LazyProfile = lazy(() => import("./components/Profile"));

const SafeLazyComponent = withErrorBoundary(
  lazy(() => import("./components/SafeComponent")),
);

const App: React.FC = () => {
  return (
    <div>
      <Suspense fallback={<div>Loading...</div>}>
        <LazyComponent />
      </Suspense>

      <Suspense fallback={<div>Loading Dashboard...</div>}>
        <LazyDashboard />
      </Suspense>
    </div>
  );
};

async function loadAndWrapComponent(
  componentPath: string,
): Promise<ComponentType<any>> {
  const module = await import(componentPath);
  const Component = module.default;

  return withAuth(withLayout(Component));
}

function createLazyAuthComponent(importPath: string): ComponentType<any> {
  const LazyComp = lazy(() => import(importPath));
  return withAuth(withLayout(LazyComp));
}

function withConditionalAuth<P extends object>(
  Component: ComponentType<P>,
  requireAuth: boolean,
): ComponentType<P> {
  if (requireAuth) {
    return withAuth(Component);
  }
  return Component;
}

function composeHOCs<P extends object>(
  Component: ComponentType<P>,
  options: {
    auth?: boolean;
    layout?: boolean;
    logging?: boolean;
  },
): ComponentType<any> {
  let Wrapped: ComponentType<any> = Component;

  if (options.logging) {
    Wrapped = withLogging(Wrapped);
  }
  if (options.layout) {
    Wrapped = withLayout(Wrapped);
  }
  if (options.auth) {
    Wrapped = withAuth(Wrapped);
  }

  return Wrapped;
}

async function loadRouteComponent(route: string): Promise<ComponentType<any>> {
  switch (route) {
    case "/admin":
      return (await import("./pages/AdminPage")).default;
    case "/dashboard":
      return (await import("./pages/DashboardPage")).default;
    case "/profile":
      return (await import("./pages/ProfilePage")).default;
    case "/settings":
      return (await import("./pages/SettingsPage")).default;
    default:
      return (await import("./pages/NotFoundPage")).default;
  }
}

const LazyRoutes: Record<string, ComponentType<any>> = {
  admin: lazy(() => import("./pages/AdminPage")),
  dashboard: lazy(() => import("./pages/DashboardPage")),
  profile: lazy(() => import("./pages/ProfilePage")),
  settings: lazy(() => import("./pages/SettingsPage")),
};

function withDynamicAnalytics<P extends object>(
  Component: ComponentType<P>,
): ComponentType<P> {
  return (props: P) => {
    React.useEffect(() => {
      import("./utils/analytics").then((analytics) => {
        analytics.trackPageView(Component.name);
      });
    }, []);

    return <Component {...props} />;
  };
}

const TrackedComponent = withDynamicAnalytics(
  withAuth(withLayout(BaseComponent)),
);

export {
  BaseComponent,
  UserProfile,
  withAuth,
  withLayout,
  withLogging,
  withErrorBoundary,
  withData,
  AuthenticatedLayout,
  LoggedAuthComponent,
  TripleWrappedComponent,
  QuadrupleWrappedComponent,
  ExtremelyWrappedComponent,
  loadModule,
  loadConditionalModule,
  loadModuleSafely,
  loadMultipleModules,
  LazyComponent,
  LazyDashboard,
  LazySettings,
  LazyProfile,
  SafeLazyComponent,
  App,
  loadAndWrapComponent,
  createLazyAuthComponent,
  withConditionalAuth,
  composeHOCs,
  loadRouteComponent,
  LazyRoutes,
  withDynamicAnalytics,
  TrackedComponent,
};
