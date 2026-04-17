//+------------------------------------------------------------------+
//|                                                     UT_Trail.mq5 |
//|                     UT Bot Trailing Stop Indicator                |
//|                    ATR Period = 1, Key Value = 2.0                |
//+------------------------------------------------------------------+
#property copyright "Trading Bot"
#property link      "https://www.mql5.com"
#property version   "2.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1

//--- plot Trail
#property indicator_label1  "UT Trail"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrRed
#property indicator_style1  STYLE_DOT
#property indicator_width1  2

//--- indicator buffers
double UtTrailBuffer[];

//--- input parameters
input int      ATR_Period = 1;        // ATR Period (1 = single bar range)
input double   Key_Value = 2.0;       // Key Value Multiplier

//+------------------------------------------------------------------+
//| Custom indicator initialization function                         |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- indicator buffers mapping
   SetIndexBuffer(0, UtTrailBuffer, INDICATOR_DATA);
   PlotIndexSetInteger(0, PLOT_DRAW_BEGIN, 2);
   
   //--- set short name
   IndicatorSetString(INDICATOR_SHORTNAME, "UT Trail (ATR=" + (string)ATR_Period + ", Key=" + DoubleToString(Key_Value, 1) + ")");
   
   //--- set label
   PlotIndexSetString(0, PLOT_LABEL, "UT Trail");
   
   //--- set initial empty value
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, 0);
   
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
   //--- check minimum bars
   if(rates_total < 3)
      return(0);

   //--- starting index
   int start = (prev_calculated == 0) ? 2 : prev_calculated - 1;

   //--- main calculation loop
   for(int i = start; i < rates_total; i++)
   {
      //--- Calculate ATR for current bar (for ATR_Period=1, this is just high-low)
      double atr = high[i] - low[i];
      
      //--- n_loss = Key_Value * ATR
      double n_loss = Key_Value * atr;
      
      //--- Get previous trail value
      double prev_trail = UtTrailBuffer[i - 1];
      
      //--- Determine trend direction
      bool is_uptrend = close[i] > prev_trail;
      bool was_uptrend = close[i - 1] > prev_trail;
      
      //--- Calculate new trail
      double new_trail;
      
      if(is_uptrend && was_uptrend)
      {
         //--- Continue uptrend: trail goes UP only
         new_trail = MathMax(prev_trail, close[i] - n_loss);
      }
      else if(!is_uptrend && !was_uptrend)
      {
         //--- Continue downtrend: trail goes DOWN only
         new_trail = MathMin(prev_trail, close[i] + n_loss);
      }
      else if(is_uptrend)
      {
         //--- Switch to uptrend
         new_trail = close[i] - n_loss;
      }
      else
      {
         //--- Switch to downtrend
         new_trail = close[i] + n_loss;
      }
      
      //--- Set the buffer value
      UtTrailBuffer[i] = new_trail;
   }

   //--- return value of prev_calculated for next call
   return(rates_total);
}
//+------------------------------------------------------------------+
