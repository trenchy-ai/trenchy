
export default {
  mode: "development",
  entry: "./script.ts",
  output: {
    path: process.cwd(),
    filename: 'script.js'
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: "ts-loader",
        exclude: /node_modules/,
      },
    ],
  },
};
