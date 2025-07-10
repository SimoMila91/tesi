#include "pmsis.h"   // drivers
#include "bsp/bsp.h" // pad configurations for connecting to memory, cameta, etc.
#include "cpx.h"     // to send and receive packets
#include "wifi.h"
#include <stdio.h>

#define CUSTOM_COMM_PORT 0x1388 // 5000

static int wifiConnected = 0;
static int wifiClientConnected = 0;
static void cpxPacketCallback(const CPXPacket_t *cpxRx);

static CPXPacket_t rxp;
static CPXPacket_t txp;

void handleReceiveMessage(uint8_t *data, uint32_t length)
{
  cpxPrintToConsole(LOG_TO_CRTP, "Received message: %.*s\n", length, data);

  // prepare response
  char response[64];
  int response_len = snprintf(response, sizeof(response), "Messaggio ricevuto: %.*s", length, data);

  // send response back
  cpxInitRoute(CPX_T_GAP8, CPX_T_WIFI_HOST, CPX_F_APP, &txp.route);
  memcpy(txp.data, response, response_len);
  txp.dataLength = response_len;
  cpxSendPacketBlocking(&txp);
}

void rx_task(void *parameters)
{
  while (1)
  {
    cpxReceivePacketBlocking(CPX_F_WIFI_CTRL, &rxp); // Blocca fino a ricezione
    WiFiCTRLPacket_t *wifiCtrl = (WiFiCTRLPacket_t *)rxp.data;

    switch (wifiCtrl->cmd)
    {
    case WIFI_CTRL_STATUS_WIFI_CONNECTED:
      cpxPrintToConsole(LOG_TO_CRTP, "WiFi connected (%u.%u.%u.%u)\n", wifiCtrl->data[0], wifiCtrl->data[1], wifiCtrl->data[2], wifiCtrl->data[3]);
      wifiConnected = 1;
      break;
    case WIFI_CTRL_STATUS_CLIENT_CONNECTED:
      cpxPrintToConsole(LOG_TO_CRTP, "Wifi client connection status: %u\n", wifiCtrl->data[0]);
      wifiClientConnected = wifiCtrl->data[0];
      break;
    default:
      break;
    }
  }
}

void comm_task(void *parameters)
{
  // Initialize the route for our communication packets
  cpxInitRoute(CPX_T_GAP8, CPX_T_WIFI_HOST, CPX_F_APP, &txp.route);

  cpxPrintToConsole(LOG_TO_CRTP, "Communication task started. Waiting for messages...\n");

  while (1)
  {
    if (wifiClientConnected)
    {
      // wait for incoming messages
      // cpxReceivePacketBlocking(CPX_F_APP, &rxp); // Blocca fino a ricezione

      if (rxp.route.source == CPX_T_WIFI_HOST)
      {
        // Handle the received message
        handleReceiveMessage(rxp.data, rxp.dataLength);
      }
      else
      {
        cpxPrintToConsole(LOG_TO_CRTP, "Received message from unknown source: %d\n", rxp.route.source);
        vTaskDelay(100);
      }
    }
    else
    {
      vTaskDelay(100);
    }
  }
}

void comm_task(void *parameters)
{
  // Initialize the route for our communication packets
  cpxInitRoute(CPX_T_GAP8, CPX_T_WIFI_HOST, CPX_F_APP, &txp.route);

  cpxPrintToConsole(LOG_TO_CRTP, "Communication task started. Sending periodic messages...\n");

  while (1)
  {
    if (wifiClientConnected)
    {
      // Prepare and send message
      const char *message = "Hello from Crazyflie";
      size_t msg_len = strlen(message);
      memcpy(txp.data, message, msg_len);
      txp.dataLength = msg_len;

      cpxSendPacketBlocking(&txp);
      cpxPrintToConsole(LOG_TO_CRTP, "Sent message to client: %s\n", message);
    }

    // Wait a bit before sending again
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

void start_example(void)
{
  struct pi_uart_conf conf;
  struct pi_device device;
  pi_uart_conf_init(&conf);
  conf.baudrate_bps = 115200;
  cpxRegisterAppMessageHandler(cpxPacketCallback);

  pi_open_from_conf(&device, &conf);
  if (pi_uart_open(&device))
  {
    printf("[UART] open failed !\n");
    pmsis_exit(-1);
  }

  cpxInit();
  cpxEnableFunction(CPX_F_WIFI_CTRL);
  cpxEnableFunction(CPX_F_APP);

  cpxPrintToConsole(LOG_TO_CRTP, "-- WiFi Communication Example --\n");
  cpxPrintToConsole(LOG_TO_CRTP, "Listening on port 0x%02X\n", CUSTOM_COMM_PORT);

  BaseType_t xTask;

  xTask = xTaskCreate(rx_task, "rx_task", configMINIMAL_STACK_SIZE * 2,
                      NULL, tskIDLE_PRIORITY + 1, NULL);
  if (xTask != pdPASS)
  {
    cpxPrintToConsole(LOG_TO_CRTP, "RX task did not start!\n");
    pmsis_exit(-1);
  }

  xTask = xTaskCreate(comm_task, "comm_task", configMINIMAL_STACK_SIZE * 4,
                      NULL, tskIDLE_PRIORITY + 2, NULL);
  if (xTask != pdPASS)
  {
    cpxPrintToConsole(LOG_TO_CRTP, "Communication task did not start!\n");
    pmsis_exit(-1);
  }
  else
  {
    cpxPrintToConsole(LOG_TO_CRTP, "Communication task started!\n");
  }

  while (1)
  {
    pi_yield();
  }
}

int main(void)
{
  pi_bsp_init();
  // Increase the FC freq to 250 MHz
  pi_freq_set(PI_FREQ_DOMAIN_FC, 250000000);
  __pi_pmu_voltage_set(PI_PMU_DOMAIN_FC, 1200);
  return pmsis_kickoff((void *)start_example);
}

static void cpxPacketCallback(const CPXPacket_t *cpxRx)
{
  DEBUG_PRINT("Got packet from ROUTER PC (%u)\n", cpxRx->data[0]);
}