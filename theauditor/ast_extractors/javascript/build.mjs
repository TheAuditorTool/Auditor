/**
 * esbuild configuration for JS extractor.
 *
 * Externalizes optional template engine dependencies from @vue/compiler-sfc
 * that are dynamically required but not needed for SFC parsing.
 */
import * as esbuild from 'esbuild';

// Optional template engines from @vue/compiler-sfc that we don't need
// These are dynamically required by consolidate.js but not used for SFC parsing
const VUE_OPTIONAL_EXTERNALS = [
  // Template engines from consolidate.js used by @vue/compiler-sfc
  'velocityjs',
  'dustjs-linkedin',
  'atpl',
  'liquor',
  'twig',
  'ejs',
  'eco',
  'jazz',
  'jqtpl',
  'hamljs',
  'hamlet',
  'whiskers',
  'haml-coffee',
  'hogan.js',
  'templayed',
  'walrus',
  'mustache',
  'just',
  'ect',
  'mote',
  'toffee',
  'dot',
  'bracket-template',
  'ractive',
  'nunjucks',
  'htmling',
  'babel-core',
  'plates',
  'react-dom/server',
  'react',
  'arc-templates',
  'vash',
  'slm',
  'marko',
  'teacup/lib/express',
  'coffee-script',
  'squirrelly',
  'twing',
  'handlebars',
  'underscore',
  'lodash',
  'pug',
  'then-pug',
  'jade',
  'then-jade',
  'haml',
  'swig',
  'swig-templates',
];

await esbuild.build({
  entryPoints: ['src/main.ts'],
  bundle: true,
  platform: 'node',
  target: 'node18',
  format: 'cjs',
  outfile: 'dist/extractor.cjs',
  external: VUE_OPTIONAL_EXTERNALS,
});

console.log('Build complete: dist/extractor.cjs');
