/**
 * Higher-Order Components (HOCs) and Dynamic Imports Fixture (TypeScript/React)
 *
 * Tests extraction of:
 * - Nested HOCs: withAuth(withLayout(withLogging(Component)))
 * - Dynamic import() expressions
 * - React.lazy() for code splitting
 * - Conditional imports
 * - HOC type definitions
 * - Component wrapping chains
 *
 * Validates call chain resolution through HOC wrappers and dynamic imports.
 */

import React, {ComponentType, lazy, Suspense} from 'react';

// ==============================================================================
// Base Components
// ==============================================================================

interface BaseComponentProps {
  title: string;
  content?: string;
}

/**
 * Base component to be wrapped by HOCs.
 */
const BaseComponent: React.FC<BaseComponentProps> = ({ title, content }) => {
  return (
    <div>
      <h1>{title}</h1>
      <p>{content}</p>
    </div>
  );
};

/**
 * Another base component.
 */
const UserProfile: React.FC<{ userId: number }> = ({ userId }) => {
  return <div>User {userId}</div>;
};

// ==============================================================================
// Higher-Order Component Definitions
// ==============================================================================

/**
 * Authentication HOC - adds auth checking.
 * Tests: Basic HOC pattern.
 */
function withAuth<P extends object>(
  Component: ComponentType<P>
): ComponentType<P> {
  return (props: P) => {
    const isAuthenticated = true; // Simplified auth check

    if (!isAuthenticated) {
      return <div>Please log in</div>;
    }

    return <Component {...props} />;
  };
}

/**
 * Layout HOC - wraps component in layout.
 * Tests: HOC with additional props.
 */
interface WithLayoutProps {
  layoutType?: 'default' | 'sidebar' | 'fullscreen';
}

function withLayout<P extends object>(
  Component: ComponentType<P>
): ComponentType<P & WithLayoutProps> {
  return ({ layoutType = 'default', ...props }: P & WithLayoutProps) => {
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

/**
 * Logging HOC - logs component lifecycle.
 * Tests: HOC with side effects.
 */
function withLogging<P extends object>(
  Component: ComponentType<P>
): ComponentType<P> {
  return (props: P) => {
    React.useEffect(() => {
      console.log(`Component mounted with props:`, props);
      return () => console.log(`Component unmounting`);
    }, [props]);

    return <Component {...props} />;
  };
}

/**
 * Error boundary HOC.
 * Tests: Class-based HOC.
 */
function withErrorBoundary<P extends object>(
  Component: ComponentType<P>
): ComponentType<P> {
  return class ErrorBoundary extends React.Component<P, { hasError: boolean }> {
    state = { hasError: false };

    static getDerivedStateFromError() {
      return { hasError: true };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
      console.error('Error caught:', error, errorInfo);
    }

    render() {
      if (this.state.hasError) {
        return <div>Something went wrong</div>;
      }
      return <Component {...this.props} />;
    }
  };
}

/**
 * Data fetching HOC.
 * Tests: HOC with async operations.
 */
interface WithDataProps<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

function withData<P extends object, T = any>(
  fetcher: () => Promise<T>
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

      return <Component {...props} data={data} loading={loading} error={error} />;
    };
  };
}

// ==============================================================================
// Nested HOCs (2-level nesting)
// ==============================================================================

/**
 * Component with 2 nested HOCs.
 * Tests: withAuth(withLayout(BaseComponent))
 */
const AuthenticatedLayout = withAuth(withLayout(BaseComponent));

/**
 * Component with 2 nested HOCs (different order).
 * Tests: withLogging(withAuth(BaseComponent))
 */
const LoggedAuthComponent = withLogging(withAuth(BaseComponent));

// ==============================================================================
// Deeply Nested HOCs (3+ levels)
// ==============================================================================

/**
 * Component with 3 nested HOCs.
 * Tests: withAuth(withLayout(withLogging(BaseComponent)))
 */
const TripleWrappedComponent = withAuth(
  withLayout(
    withLogging(BaseComponent)
  )
);

/**
 * Component with 4 nested HOCs.
 * Tests: withAuth(withLayout(withLogging(withErrorBoundary(BaseComponent))))
 */
const QuadrupleWrappedComponent = withAuth(
  withLayout(
    withLogging(
      withErrorBoundary(BaseComponent)
    )
  )
);

/**
 * Component with 5 nested HOCs (extreme nesting).
 * Tests: Deep HOC chain resolution.
 */
const ExtremelyWrappedComponent = withErrorBoundary(
  withAuth(
    withLayout(
      withLogging(
        withData<BaseComponentProps, any>(() => Promise.resolve({ data: 'test' }))(
          BaseComponent
        )
      )
    )
  )
);

// ==============================================================================
// Dynamic Imports (import() expressions)
// ==============================================================================

/**
 * Dynamic import function.
 * Tests: import() expression with string literal.
 */
async function loadModule(moduleName: string): Promise<any> {
  const module = await import('./components/DynamicModule');
  return module.default;
}

/**
 * Conditional dynamic import.
 * Tests: Dynamic import based on condition.
 */
async function loadConditionalModule(useAdmin: boolean): Promise<any> {
  if (useAdmin) {
    const adminModule = await import('./components/AdminModule');
    return adminModule.default;
  } else {
    const userModule = await import('./components/UserModule');
    return userModule.default;
  }
}

/**
 * Dynamic import with error handling.
 * Tests: try/catch around dynamic import.
 */
async function loadModuleSafely(moduleName: string): Promise<any> {
  try {
    const module = await import(`./components/${moduleName}`);
    return module.default;
  } catch (error) {
    console.error(`Failed to load module: ${moduleName}`, error);
    return null;
  }
}

/**
 * Multiple dynamic imports in parallel.
 * Tests: Promise.all with dynamic imports.
 */
async function loadMultipleModules(): Promise<any[]> {
  const [module1, module2, module3] = await Promise.all([
    import('./components/Module1'),
    import('./components/Module2'),
    import('./components/Module3')
  ]);

  return [module1.default, module2.default, module3.default];
}

// ==============================================================================
// React.lazy (Code Splitting)
// ==============================================================================

/**
 * Lazy-loaded component using React.lazy.
 * Tests: React.lazy() with dynamic import.
 */
const LazyComponent = lazy(() => import('./components/LazyLoadedComponent'));

/**
 * Multiple lazy components.
 * Tests: Multiple React.lazy declarations.
 */
const LazyDashboard = lazy(() => import('./components/Dashboard'));
const LazySettings = lazy(() => import('./components/Settings'));
const LazyProfile = lazy(() => import('./components/Profile'));

/**
 * Lazy component with error boundary.
 * Tests: Lazy loading combined with HOC.
 */
const SafeLazyComponent = withErrorBoundary(
  lazy(() => import('./components/SafeComponent'))
);

/**
 * Component using lazy-loaded components.
 * Tests: Suspense with lazy components.
 */
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

// ==============================================================================
// Dynamic Import with HOCs
// ==============================================================================

/**
 * Function that dynamically imports and wraps with HOCs.
 * Tests: Combining dynamic imports with HOCs.
 */
async function loadAndWrapComponent(
  componentPath: string
): Promise<ComponentType<any>> {
  const module = await import(componentPath);
  const Component = module.default;

  // Wrap the dynamically imported component with HOCs
  return withAuth(withLayout(Component));
}

/**
 * Factory function for HOC-wrapped lazy components.
 * Tests: Higher-order function returning lazy component with HOCs.
 */
function createLazyAuthComponent(
  importPath: string
): ComponentType<any> {
  const LazyComp = lazy(() => import(importPath));
  return withAuth(withLayout(LazyComp));
}

// ==============================================================================
// Conditional HOC Application
// ==============================================================================

/**
 * Apply HOC conditionally.
 * Tests: Conditional HOC wrapping.
 */
function withConditionalAuth<P extends object>(
  Component: ComponentType<P>,
  requireAuth: boolean
): ComponentType<P> {
  if (requireAuth) {
    return withAuth(Component);
  }
  return Component;
}

/**
 * Apply multiple HOCs conditionally.
 * Tests: Dynamic HOC composition.
 */
function composeHOCs<P extends object>(
  Component: ComponentType<P>,
  options: {
    auth?: boolean;
    layout?: boolean;
    logging?: boolean;
  }
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

// ==============================================================================
// Route-based Dynamic Imports
// ==============================================================================

/**
 * Load component based on route.
 * Tests: Switch-case dynamic imports.
 */
async function loadRouteComponent(route: string): Promise<ComponentType<any>> {
  switch (route) {
    case '/admin':
      return (await import('./pages/AdminPage')).default;
    case '/dashboard':
      return (await import('./pages/DashboardPage')).default;
    case '/profile':
      return (await import('./pages/ProfilePage')).default;
    case '/settings':
      return (await import('./pages/SettingsPage')).default;
    default:
      return (await import('./pages/NotFoundPage')).default;
  }
}

/**
 * Lazy route components map.
 * Tests: Object mapping with lazy components.
 */
const LazyRoutes: Record<string, ComponentType<any>> = {
  admin: lazy(() => import('./pages/AdminPage')),
  dashboard: lazy(() => import('./pages/DashboardPage')),
  profile: lazy(() => import('./pages/ProfilePage')),
  settings: lazy(() => import('./pages/SettingsPage'))
};

// ==============================================================================
// HOC with Dynamic Import Inside
// ==============================================================================

/**
 * HOC that dynamically imports utilities.
 * Tests: Dynamic import inside HOC definition.
 */
function withDynamicAnalytics<P extends object>(
  Component: ComponentType<P>
): ComponentType<P> {
  return (props: P) => {
    React.useEffect(() => {
      // Dynamically import analytics module
      import('./utils/analytics').then((analytics) => {
        analytics.trackPageView(Component.name);
      });
    }, []);

    return <Component {...props} />;
  };
}

/**
 * Component with dynamic analytics HOC.
 * Tests: HOC that uses dynamic imports internally.
 */
const TrackedComponent = withDynamicAnalytics(
  withAuth(
    withLayout(BaseComponent)
  )
);

// ==============================================================================
// Export All
// ==============================================================================

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
  TrackedComponent
};
