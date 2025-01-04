import path from 'path';
import CopyPlugin from 'copy-webpack-plugin';
import HtmlMinimizerPlugin from 'html-minimizer-webpack-plugin';


export default {
  mode: 'production',
  entry: './src/script.ts',
  output: {
    path: path.join(process.cwd(), 'dist'),
    filename: 'script.js',
  },
  module: {
    rules: [{
      test: /\.ts$/,
      use: 'ts-loader',
      exclude: /node_modules/,
    }],
  },
  plugins: [
    new CopyPlugin({
      patterns: [{
        context: 'src',
        from: '*.html',
      }],
    }),
  ],
  optimization: {
    minimizer: [`...`, new HtmlMinimizerPlugin()],
  },
};
