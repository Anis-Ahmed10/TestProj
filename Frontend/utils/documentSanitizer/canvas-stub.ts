// Stub module for pdfjs-dist's optional 'canvas' dependency.
// pdfjs-dist conditionally requires Node's 'canvas' package for server-side
// rendering, which is unavailable in the browser. This empty module satisfies
// the bundler's resolution without introducing any runtime behavior.
export default {};
