//+------------------------------------------------------------------+
//|                                            UT_Trail_RedLine.mq5 |
//|                                  Copyright 2024, Trading Bot    |
//|                                                                  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2024, Trading Bot"
#property link      ""
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1

//--- plot UT Trail
#property indicator_label1  "UT Trail"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrRed
#property indicator_style1  STYLE_DOT
#property indicator_width1  2

//--- input parameters
input double   KeyValue = 1.0;        // UT Bot Key Value
input int      ATRPeriod = 1;         // ATR Period (1 = single candle range)

//--- indicator buffers
double UTTrailBuffer[];

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- indicator buffers mapping
   SetIndexBuffer(0, UTTrailBuffer, INDICATOR_DATA);
   
   //--- set precision
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);
   
   //--- set short name
   IndicatorSetString(INDICATOR_SHORTNAME, "UT Trail Red Line");
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Custom indicator iteration function                              |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   //--- check for minimum bars
   if(rates_total < 2)
      return(0);
      
   //--- determine starting position
   int start = prev_calculated;
   if(start < 1)
      start = 1;
   
   //--- calculate UT Trail
   for(int i = start; i < rates_total; i++)
   {
      if(i == 0)
      {
         UTTrailBuffer[i] = close[i];
         continue;
      }
      
      // Calculate ATR (single candle range)
      double atr = MathAbs(high[i] - low[i]);
      double n_loss = KeyValue * atr;
      
      double prev_stop = UTTrailBuffer[i-1];
      double prev_close = close[i-1];
      
      // UT Bot logic
      if(close[i] > prev_stop && prev_close > prev_stop)
      {
         UTTrailBuffer[i] = MathMax(prev_stop, close[i] - n_loss);
      }
      else if(close[i] < prev_stop && prev_close < prev_stop)
      {
         UTTrailBuffer[i] = MathMin(prev_stop, close[i] + n_loss);
      }
      else if(close[i] > prev_stop)
      {
         UTTrailBuffer[i] = close[i] - n_loss;
      }
      else
      {
         UTTrailBuffer[i] = close[i] + n_loss;
      }
   }
   
   //--- return value of prev_calculated for next call
   return(rates_total);
}
//+------------------------------------------------------------------+