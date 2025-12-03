import React from 'react';
import { Global, css } from '@emotion/react';

const GlobalStyles: React.FC = () => (
  <Global
    styles={css`
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        min-height: 100vh;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
        color: #1f1f1f;
      }
    `}
  />
);

export default GlobalStyles;
